"""Copy a rendered post into a phone-friendly inbox in carousel order.

TikTok on iOS reads from the photo library, not the Mac render tree. Staging
renames slides to zero-padded order so Files and Photos keep the swipe sequence.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from tiktoks.video import VideoError, load_manifest, resolve_post_dir, slide_files


class StageError(RuntimeError):
    """Staging failed before anything was copied."""


def icloud_inbox_root() -> Path | None:
    root = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs"
    if not root.is_dir():
        return None
    return root / "TikTok Inbox"


def default_inbox_root() -> Path:
    icloud = icloud_inbox_root()
    if icloud is not None:
        return icloud
    from tiktoks.config import REVIEW_DIR

    return REVIEW_DIR / "phone-inbox"


def stage_destination(post_dir: Path | str, dest: Path | str | None = None) -> Path:
    directory = resolve_post_dir(post_dir)
    manifest = load_manifest(directory)
    slug = manifest.get("slug") or directory.name
    if dest is None:
        return default_inbox_root() / slug
    return Path(dest)


def stage_post(
    post_dir: Path | str,
    *,
    dest: Path | str | None = None,
    clean: bool = True,
    import_photos: bool = False,
) -> list[Path]:
    """Copy slides in manifest order. Returns the staged file paths."""
    directory = resolve_post_dir(post_dir)
    try:
        rows = slide_files(directory)
    except VideoError as exc:
        raise StageError(str(exc)) from exc

    manifest = load_manifest(directory)
    out_dir = stage_destination(directory, dest)
    if out_dir.exists() and clean:
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    staged: list[Path] = []
    for index, (source, kind, _) in enumerate(rows, start=1):
        target = out_dir / f"{index:02d}-{kind}.png"
        shutil.copy2(source, target)
        staged.append(target)

    caption = manifest.get("caption")
    if caption:
        (out_dir / "caption.txt").write_text(str(caption).strip() + "\n", encoding="utf-8")

    meta = {
        "slug": manifest.get("slug"),
        "title": manifest.get("title"),
        "slide_count": len(staged),
        "source_dir": str(directory),
    }
    (out_dir / "post.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    if import_photos:
        import_to_photos(staged)
    return staged


def import_to_photos(paths: list[Path]) -> None:
    if not paths:
        return
    if shutil.which("osascript") is None:
        raise StageError("osascript is required to import into Photos")
    posix = ", ".join(f'POSIX file "{path}"' for path in paths)
    script = f'tell application "Photos" to import {{{posix}}}'
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise StageError(f"Photos import failed: {detail or exc}") from exc
