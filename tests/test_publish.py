"""TikTok publish log and status."""

import json
from datetime import date
from pathlib import Path

import pytest

from tiktoks.publish import (
    PublishError,
    format_status,
    parse_post_id,
    record_tiktok,
    resolve_target,
    status_rows,
    write_log,
)


def _manifest(directory: Path, slug: str, **overrides) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "slug": slug,
        "format": "geo-quiz",
        "theme": "night",
        "difficulty": "easy",
        "title": slug,
        "publish": {
            "post_id": None,
            "url": None,
            "posted_at": None,
            "notes": None,
            "youtube": {"video_id": None, "url": None, "posted_at": None},
        },
    }
    payload.update(overrides)
    path = directory / "post.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def test_parse_post_id_from_url():
    url = "https://www.tiktok.com/@matt/video/1234567890123456789"
    assert parse_post_id(url) == "1234567890123456789"
    assert parse_post_id("https://example.com/nope") is None


def test_record_tiktok_writes_manifest_and_csv(tmp_path: Path):
    post = tmp_path / "posts" / "geo-quiz" / "geo-easy-001" / "night"
    _manifest(post, "geo-easy-001", title="Easy geography quiz")
    log = tmp_path / "publish.csv"

    row = record_tiktok(
        "geo-easy-001",
        posted_at=date(2026, 9, 19),
        url="https://www.tiktok.com/@matt/video/99",
        notes="asked for more islands",
        root=tmp_path / "posts",
        log_path=log,
    )
    saved = json.loads((post / "post.json").read_text(encoding="utf-8"))
    assert saved["publish"]["posted_at"] == "2026-09-19"
    assert saved["publish"]["post_id"] == "99"
    assert saved["publish"]["notes"] == "asked for more islands"
    assert row["slug"] == "geo-easy-001"
    text = log.read_text(encoding="utf-8")
    assert "geo-easy-001" in text
    assert "asked for more islands" in text


def test_record_tiktok_keeps_youtube_id(tmp_path: Path):
    post = tmp_path / "posts" / "demo" / "night"
    _manifest(
        post,
        "demo",
        publish={
            "post_id": None,
            "posted_at": None,
            "youtube": {
                "video_id": "yt-1",
                "url": "https://youtu.be/yt-1",
                "posted_at": "2026-09-06",
            },
        },
    )
    record_tiktok(
        "demo",
        posted_at="2026-09-19",
        root=tmp_path / "posts",
        log_path=tmp_path / "log.csv",
    )
    saved = json.loads((post / "post.json").read_text(encoding="utf-8"))
    assert saved["publish"]["youtube"]["video_id"] == "yt-1"
    assert saved["publish"]["posted_at"] == "2026-09-19"


def test_already_posted_needs_force(tmp_path: Path):
    post = tmp_path / "posts" / "demo" / "night"
    _manifest(post, "demo", publish={"posted_at": "2026-09-01"})
    with pytest.raises(PublishError, match="already marked"):
        record_tiktok("demo", root=tmp_path / "posts", log_path=tmp_path / "log.csv")
    record_tiktok(
        "demo",
        posted_at="2026-09-19",
        force=True,
        root=tmp_path / "posts",
        log_path=tmp_path / "log.csv",
    )
    saved = json.loads((post / "post.json").read_text(encoding="utf-8"))
    assert saved["publish"]["posted_at"] == "2026-09-19"


def test_ambiguous_slug_needs_theme_or_dir(tmp_path: Path):
    _manifest(tmp_path / "posts" / "demo" / "night", "demo", theme="night")
    _manifest(tmp_path / "posts" / "demo" / "paper", "demo", theme="paper")
    with pytest.raises(PublishError, match="more than one render"):
        resolve_target("demo", root=tmp_path / "posts")
    night = resolve_target("demo", root=tmp_path / "posts", theme="night")
    assert night.parent.name == "night"


def test_alias_typo_resolves(tmp_path: Path):
    _manifest(tmp_path / "posts" / "geo-silhouette-easy-001" / "night", "geo-silhouette-easy-001")
    path = resolve_target("geo-silhoutte-easy-001", root=tmp_path / "posts")
    assert path.parent.parent.name == "geo-silhouette-easy-001"


def test_status_splits_published_and_queue(tmp_path: Path):
    ready = tmp_path / "posts" / "ready" / "night"
    waiting = tmp_path / "posts" / "waiting" / "night"
    _manifest(ready, "ready", publish={"posted_at": "2026-09-05"})
    _manifest(waiting, "waiting")
    log = tmp_path / "publish.csv"
    write_log(root=tmp_path / "posts", log_path=log)
    # A post that went out before it had a post.json.
    log.write_text(
        log.read_text(encoding="utf-8") + "2026-09-09,old-story,story,,,,old-story,,,,\n",
        encoding="utf-8",
    )

    all_rows = status_rows(tmp_path / "posts", log)
    slugs = [row["slug"] for row in all_rows]
    assert slugs == ["ready", "old-story", "waiting"]
    unpublished = status_rows(tmp_path / "posts", log, unpublished=True)
    assert [row["slug"] for row in unpublished] == ["waiting"]
    published = status_rows(tmp_path / "posts", log, published=True)
    assert [row["slug"] for row in published] == ["ready", "old-story"]
    text = format_status(all_rows)
    assert "ready" in text
    assert "2 on TikTok" in text


def test_write_log_keeps_orphan_rows(tmp_path: Path):
    post = tmp_path / "posts" / "demo" / "night"
    _manifest(post, "demo")
    log = tmp_path / "publish.csv"
    log.write_text(
        "posted_at,slug,format,difficulty,theme,title,post_id,url,notes,youtube_id,youtube_posted_at\n"
        "2026-09-09,ghost,story,,,,Ghost,,,,\n",
        encoding="utf-8",
    )
    record_tiktok("demo", posted_at="2026-09-19", root=tmp_path / "posts", log_path=log)
    slugs = [line.split(",")[1] for line in log.read_text(encoding="utf-8").splitlines()[1:]]
    assert slugs == ["ghost", "demo"]
