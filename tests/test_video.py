"""Video assembly from a post.json slide list."""

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest
from PIL import Image

from tiktoks.post import merge_publish
from tiktoks.video import (
    VideoError,
    assemble,
    beds,
    concat_script,
    hold_for,
    music_attribution,
    resolve_bed,
    slide_files,
    total_duration,
)
from tiktoks.youtube import record_upload


def _png(path: Path) -> None:
    Image.new("RGB", (108, 192), "black").save(path)


def _post(tmp_path: Path) -> Path:
    for name in ("cover.png", "prompt.png", "answer.png"):
        _png(tmp_path / name)
    (tmp_path / "post.json").write_text(
        """
        {
          "slug": "demo",
          "slides": [
            {"file": "cover.png", "kind": "cover"},
            {"file": "prompt.png", "kind": "prompt"},
            {"file": "answer.png", "kind": "answer"}
          ]
        }
        """.strip(),
        encoding="utf-8",
    )
    return tmp_path


def test_holds_differ_by_kind():
    assert hold_for("prompt") > hold_for("answer")
    assert hold_for("mystery") > hold_for("cover")
    assert hold_for("unknown") == hold_for("slide")


def test_concat_repeats_the_last_file(tmp_path):
    rows = slide_files(_post(tmp_path))
    script = concat_script(rows)
    assert script.count("cover.png") == 1
    assert script.count("answer.png") == 2
    assert "duration 4.0" in script
    assert total_duration(rows) == 2.5 + 4.0 + 2.5


def test_missing_slide_fails_before_ffmpeg(tmp_path):
    _post(tmp_path)
    (tmp_path / "prompt.png").unlink()
    with pytest.raises(VideoError, match="Missing slides"):
        slide_files(tmp_path)


def test_assemble_writes_an_mp4(tmp_path):
    path = assemble(_post(tmp_path), audio=False)
    assert path.exists()
    assert path.stat().st_size > 0
    assert path.name == "demo.mp4"
    saved = json.loads((tmp_path / "post.json").read_text(encoding="utf-8"))
    assert saved["audio"] is None


def test_catalog_includes_artlist_beds():
    slugs = beds()
    assert "comfortable-mystery" in slugs
    assert "groovy-panda" in slugs
    assert "here-for-a-good-time" in slugs
    from tiktoks.config import AUDIO_DIR

    panda = AUDIO_DIR / "IamDayLight - Groovy Panda.mp3"
    if not panda.exists():
        pytest.skip("Artlist beds are not in the checkout")
    with pytest.raises(VideoError, match="license coverage"):
        resolve_bed("groovy-panda")


def test_unknown_audio_slug_fails():
    with pytest.raises(VideoError, match="Unknown audio"):
        resolve_bed("not-a-track")


def test_default_bed_has_required_credit():
    credit = music_attribution(beds()["comfortable-mystery"])
    assert credit is not None
    assert "Kevin MacLeod" in credit
    assert "Comfortable Mystery 2" in credit
    assert "creativecommons.org/licenses/by/3.0" in credit


def test_legacy_bed_blocked(tmp_path):
    with pytest.raises(VideoError, match="not reviewed"):
        assemble(_post(tmp_path), audio="comfortable-mystery")


def test_no_matching_music_requires_explicit_silence(tmp_path):
    with pytest.raises(VideoError, match="No reviewed music"):
        assemble(_post(tmp_path))


def test_reviewed_track_selection_and_changed_file(tmp_path, monkeypatch):
    from tiktoks import video

    track = tmp_path / "clean.wav"
    track.write_bytes(b"reviewed recording")
    entry = {
        "slug": "clean",
        "file": track.name,
        "license": "CC0 1.0",
        "source": "https://example.org/track",
        "license_url": "https://example.org/cc0",
        "reviewed_clean": True,
        "sha256": hashlib.sha256(track.read_bytes()).hexdigest(),
        "formats": ["geo-quiz"],
    }
    monkeypatch.setattr(video, "beds", lambda: {"clean": entry})
    monkeypatch.setattr(video, "AUDIO_DIR", tmp_path)
    assert resolve_bed(None, manifest={"format": "geo-quiz"}) == (track, entry)
    with pytest.raises(VideoError, match="No reviewed"):
        resolve_bed(None, manifest={"format": "data-story"})
    track.write_bytes(b"different recording")
    with pytest.raises(VideoError, match="changed since review"):
        resolve_bed("clean")


def test_uncataloged_audio_blocked(tmp_path):
    track = tmp_path / "unknown.mp3"
    track.write_bytes(b"audio")
    with pytest.raises(VideoError, match="Uncataloged"):
        resolve_bed(track)


def test_upload_rebuilds_existing_video_and_reloads_credit(tmp_path, monkeypatch):
    from tiktoks import youtube

    _post(tmp_path)
    (tmp_path / "demo.mp4").write_bytes(b"old video")
    calls = []

    def assemble(directory, *, audio):
        calls.append(audio)
        manifest = json.loads((directory / "post.json").read_text())
        manifest["video_sha256"] = hashlib.sha256((directory / "demo.mp4").read_bytes()).hexdigest()
        manifest["audio"] = {
            "license": "CC0 1.0",
            "source": "source",
            "license_url": "license",
            "reviewed_clean": True,
            "sha256": "checksum",
            "attribution": "New credit",
        }
        (directory / "post.json").write_text(json.dumps(manifest))
        return directory / "demo.mp4"

    class Service:
        def videos(self):
            return self

        def insert(self, **kwargs):
            assert "New credit" in kwargs["body"]["snippet"]["description"]
            return self

        def execute(self):
            return {"id": "new-video"}

    monkeypatch.setattr(youtube, "assemble", assemble)
    monkeypatch.setattr(youtube, "_service", lambda **kwargs: Service())
    monkeypatch.setattr(youtube, "_media", lambda: lambda *args, **kwargs: None)
    youtube.upload(tmp_path, audio="clean")
    assert calls == ["clean"]


def test_upload_blocks_unknown_existing_audio_before_network(tmp_path, monkeypatch):
    from tiktoks import youtube

    _post(tmp_path)
    (tmp_path / "demo.mp4").write_bytes(b"old video")
    monkeypatch.setattr(youtube, "_service", lambda **kwargs: pytest.fail("network reached"))
    with pytest.raises(youtube.YouTubeError, match="provenance missing"):
        youtube.upload(tmp_path)


def test_merge_publish_keeps_posted_ids():
    existing = {
        "post_id": "tt-1",
        "url": "https://tiktok.com/@x/video/1",
        "posted_at": "2026-09-01",
        "youtube": {
            "video_id": "yt-1",
            "url": "https://www.youtube.com/shorts/yt-1",
            "posted_at": "2026-09-06",
        },
    }
    merged = merge_publish(
        {"post_id": None, "url": None, "posted_at": None, "youtube": {"video_id": None}},
        existing,
    )
    assert merged["post_id"] == "tt-1"
    assert merged["youtube"]["video_id"] == "yt-1"


def test_pending_uploads_skips_posted_and_missing_mp4(tmp_path):
    from tiktoks.youtube import pending_uploads

    ready = tmp_path / "ready"
    ready.mkdir()
    (ready / "demo.mp4").write_bytes(b"fake")
    (ready / "post.json").write_text(
        json.dumps({"slug": "demo", "publish": {"youtube": {"video_id": None}}}),
        encoding="utf-8",
    )
    posted = tmp_path / "posted"
    posted.mkdir()
    (posted / "done.mp4").write_bytes(b"fake")
    (posted / "post.json").write_text(
        json.dumps({"slug": "done", "publish": {"youtube": {"video_id": "yt-1"}}}),
        encoding="utf-8",
    )
    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / "post.json").write_text(json.dumps({"slug": "bare"}), encoding="utf-8")
    assert pending_uploads(tmp_path) == [ready]


def test_record_upload_fills_youtube_and_leaves_tiktok(tmp_path):
    path = tmp_path / "post.json"
    path.write_text(
        json.dumps({"slug": "demo", "publish": {"post_id": "tt-1"}, "slides": []}),
        encoding="utf-8",
    )
    recorded = record_upload(path, "yt-9", when=date(2026, 9, 6))
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert recorded["video_id"] == "yt-9"
    assert saved["publish"]["post_id"] == "tt-1"
    assert saved["publish"]["youtube"]["url"].endswith("/yt-9")


def test_upload_rejects_replaced_silent_render(tmp_path, monkeypatch):
    from tiktoks import youtube

    _post(tmp_path)
    path = tmp_path / "demo.mp4"
    path.write_bytes(b"replacement with unknown audio")
    manifest_path = tmp_path / "post.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.update(audio=None, video_sha256=hashlib.sha256(b"original silent video").hexdigest())
    manifest_path.write_text(json.dumps(manifest))
    monkeypatch.setattr(youtube, "_service", lambda **kwargs: pytest.fail("network reached"))
    with pytest.raises(youtube.YouTubeError, match="Video changed"):
        youtube.upload(tmp_path)


@pytest.mark.parametrize("license_name", ["Artlist", "YouTube Audio Library"])
def test_licensed_music_requires_evidence_and_clean_review(license_name):
    from tiktoks.video import audio_approval

    entry = {
        "license": license_name,
        "source": "track page",
        "license_url": "terms",
        "reviewed_clean": True,
        "sha256": "reviewed-file-hash",
    }
    assert "license coverage" in audio_approval(entry)
    entry.update(rights_verified=True, license_evidence="saved track license and coverage details")
    assert audio_approval(entry) is None
    entry["reviewed_clean"] = False
    assert "not reviewed" in audio_approval(entry)


def test_cc_by_requires_credit():
    from tiktoks.video import audio_approval

    entry = {
        "license": "CC BY 3.0",
        "source": "track page",
        "license_url": "terms",
        "reviewed_clean": True,
        "sha256": "reviewed-file-hash",
    }
    assert "attribution" in audio_approval(entry)
    entry["attribution"] = "Full required credit"
    assert audio_approval(entry) is None


def test_preferred_music_must_match_format(monkeypatch):
    from tiktoks import video

    common = {
        "license": "CC0 1.0",
        "source": "source",
        "license_url": "license",
        "reviewed_clean": True,
        "sha256": "checksum",
    }
    monkeypatch.setattr(
        video,
        "beds",
        lambda: {
            "a-quiz": {**common, "formats": ["geo-quiz"]},
            "preferred": {**common, "formats": ["geo-quiz"]},
            "story": {**common, "formats": ["data-story"]},
        },
    )
    monkeypatch.setattr(video, "load_catalog", lambda: {"default": "preferred"})
    assert video.select_bed({"format": "geo-quiz"}) == "preferred"
    assert video.select_bed({"format": "data-story"}) == "story"
