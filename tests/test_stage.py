import json
from pathlib import Path

from PIL import Image

from tiktoks.stage import default_inbox_root, stage_post


def _png(path: Path) -> None:
    Image.new("RGB", (108, 192), "black").save(path)


def test_stage_post_copies_in_manifest_order(tmp_path: Path, monkeypatch) -> None:
    post = tmp_path / "demo"
    post.mkdir()
    _png(post / "cover.png")
    _png(post / "answer.png")
    (post / "post.json").write_text(
        json.dumps(
            {
                "slug": "demo",
                "caption": "Hello TikTok",
                "slides": [
                    {"file": "cover.png", "kind": "cover"},
                    {"file": "answer.png", "kind": "answer"},
                ],
            }
        ),
        encoding="utf-8",
    )
    inbox = tmp_path / "inbox"
    monkeypatch.setattr("tiktoks.stage.default_inbox_root", lambda: inbox)

    staged = stage_post(post, dest=inbox / "demo")
    assert [path.name for path in staged] == ["01-cover.png", "02-answer.png"]
    assert (inbox / "demo" / "caption.txt").read_text(encoding="utf-8") == "Hello TikTok\n"


def test_default_inbox_falls_back_to_review(monkeypatch) -> None:
    monkeypatch.setattr("tiktoks.stage.icloud_inbox_root", lambda: None)
    assert default_inbox_root().name == "phone-inbox"
