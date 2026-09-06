"""Video assembly from a post.json slide list."""

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
from tiktoks.youtube import _description, record_upload


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
    path, meta = resolve_bed("groovy-panda")
    assert path == panda
    assert meta["license"] == "Artlist"


def test_unknown_audio_slug_fails():
    with pytest.raises(VideoError, match="Unknown audio"):
        resolve_bed("not-a-track")


def test_default_bed_has_required_credit():
    credit = music_attribution()
    assert credit is not None
    assert "Kevin MacLeod" in credit
    assert "Comfortable Mystery 2" in credit
    assert "creativecommons.org/licenses/by/3.0" in credit


def test_assemble_with_bed_records_attribution(tmp_path):
    from tiktoks.config import AUDIO_BED_PATH

    if not AUDIO_BED_PATH.exists():
        pytest.skip("default bed is not in the checkout")
    assemble(_post(tmp_path))
    saved = json.loads((tmp_path / "post.json").read_text(encoding="utf-8"))
    assert saved["audio"]["artist"] == "Kevin MacLeod"
    assert "incompetech.com" in saved["audio"]["attribution"]
    text = _description(saved)
    assert "Comfortable Mystery 2" in text
    assert "#Shorts" in text


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
