"""Record TikTok posts and list what has gone out.

YouTube uploads write their id into `post.json` themselves. TikTok is still a
phone upload, so the TikTok fields only land if you run `tiktoks publish mark`
after posting. `data/publish.csv` is the scannable log of those marks.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import date
from pathlib import Path

from tiktoks.config import POSTS_DIR, PUBLISH_LOG_PATH
from tiktoks.post import merge_publish
from tiktoks.video import resolve_post_dir

LOG_FIELDS = [
    "posted_at",
    "slug",
    "format",
    "difficulty",
    "theme",
    "title",
    "post_id",
    "url",
    "notes",
    "youtube_id",
    "youtube_posted_at",
]

# Typos and spaces from the old slug-only log.
SLUG_ALIASES = {
    "geo-silhoutte-easy-001": "geo-silhouette-easy-001",
    "geo-silhoutte-medium-001": "geo-silhouette-medium-001",
    "geo-silhoutte-hard-001": "geo-silhouette-hard-001",
    "geo-silhoutte-expert-001": "geo-silhouette-expert-001",
    "in-n-out locations": "in-n-out-locations",
}

TIKTOK_VIDEO_RE = re.compile(r"/video/(\d+)")


class PublishError(RuntimeError):
    """Marking or looking up a post failed."""


def normalize_slug(slug: str) -> str:
    return SLUG_ALIASES.get(slug.strip(), slug.strip())


def parse_post_id(url: str | None) -> str | None:
    """Pull the numeric id off a TikTok video URL, if it is there."""
    if not url:
        return None
    match = TIKTOK_VIDEO_RE.search(url)
    return match.group(1) if match else None


def iter_manifests(root: Path | str | None = None) -> list[Path]:
    base = Path(root or POSTS_DIR)
    return sorted(path for path in base.rglob("post.json") if path.is_file())


def load_posts(root: Path | str | None = None) -> list[dict]:
    """One row per `post.json`, with publish fields pulled up for the table."""
    rows = []
    for path in iter_manifests(root):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        rows.append(_row_from_manifest(path, data))
    return rows


def find_manifests(slug: str, root: Path | str | None = None) -> list[Path]:
    wanted = normalize_slug(slug)
    matches = []
    for path in iter_manifests(root):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if data.get("slug") == wanted:
            matches.append(path)
    return matches


def resolve_target(target: str, root: Path | str | None = None, theme: str | None = None) -> Path:
    """A theme directory, a post.json, or a slug."""
    path = Path(target)
    if path.exists():
        directory = resolve_post_dir(path)
        manifest = directory / "post.json"
        if not manifest.exists():
            raise PublishError(f"No post.json in {directory}")
        return manifest

    matches = find_manifests(target, root)
    if theme:
        matches = [path for path in matches if _theme_of(path) == theme]
    if not matches:
        label = normalize_slug(target)
        if theme:
            label = f"{label} ({theme})"
        raise PublishError(f"No post.json for slug {label!r}")
    if len(matches) == 1:
        return matches[0]
    posted = [path for path in matches if _tiktok_posted(path)]
    if len(posted) == 1:
        return posted[0]
    listed = "\n  ".join(str(path.parent) for path in matches)
    raise PublishError(
        f"{normalize_slug(target)} has more than one render. Pass a directory:\n  {listed}"
    )


def record_tiktok(
    target: Path | str,
    *,
    posted_at: date | str | None = None,
    post_id: str | None = None,
    url: str | None = None,
    notes: str | None = None,
    force: bool = False,
    theme: str | None = None,
    root: Path | str | None = None,
    log_path: Path | str | None = None,
) -> dict:
    """Write TikTok publish fields into post.json and refresh the CSV log."""
    manifest = resolve_target(str(target), root=root, theme=theme)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    current = data.get("publish") if isinstance(data.get("publish"), dict) else {}
    if current.get("posted_at") and not force:
        raise PublishError(
            f"{data.get('slug')} is already marked posted {current['posted_at']}. "
            "Pass --force to change it."
        )

    when = _as_date(posted_at)
    video_id = post_id or parse_post_id(url)
    overlay = {
        "posted_at": when,
        "post_id": video_id,
        "url": url,
        "notes": notes,
    }
    data["publish"] = merge_publish(current, overlay)
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    write_log(root=root, log_path=log_path)
    return _row_from_manifest(manifest, data)


def write_log(root: Path | str | None = None, log_path: Path | str | None = None) -> Path:
    """Rewrite the CSV from current manifests, keeping rows that have no post.json."""
    path = Path(log_path or PUBLISH_LOG_PATH)
    published = [row for row in load_posts(root) if row["posted_at"]]
    seen = {(row["slug"], row["theme"] or "") for row in published}
    orphans = []
    for old in read_log(path):
        key = (old.get("slug") or "", old.get("theme") or "")
        if key not in seen and old.get("posted_at"):
            orphans.append(old)
    rows = published + orphans
    rows.sort(
        key=lambda row: (
            row.get("posted_at") or "",
            row.get("slug") or "",
            row.get("theme") or "",
        )
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LOG_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) or "" for field in LOG_FIELDS})
    return path


def read_log(log_path: Path | str | None = None) -> list[dict]:
    path = Path(log_path or PUBLISH_LOG_PATH)
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            {key: (value or None) for key, value in row.items()} for row in csv.DictReader(handle)
        ]


def status_rows(
    root: Path | str | None = None,
    log_path: Path | str | None = None,
    *,
    unpublished: bool = False,
    published: bool = False,
) -> list[dict]:
    rows = load_posts(root)
    seen = {row["slug"] for row in rows}
    for old in read_log(log_path):
        if old.get("slug") and old["slug"] not in seen:
            rows.append(
                {
                    "slug": old["slug"],
                    "format": old.get("format"),
                    "difficulty": old.get("difficulty"),
                    "theme": old.get("theme"),
                    "title": old.get("title"),
                    "posted_at": old.get("posted_at"),
                    "post_id": old.get("post_id"),
                    "url": old.get("url"),
                    "notes": old.get("notes") or "no post.json in repo",
                    "youtube_id": old.get("youtube_id"),
                    "youtube_posted_at": old.get("youtube_posted_at"),
                    "path": None,
                }
            )
            seen.add(old["slug"])

    if unpublished:
        rows = [row for row in rows if not row.get("posted_at")]
    elif published:
        rows = [row for row in rows if row.get("posted_at")]

    rows.sort(
        key=lambda row: (
            row.get("posted_at") or "9999",
            row.get("format") or "",
            row.get("slug") or "",
            row.get("theme") or "",
        )
    )
    return rows


def format_status(rows: list[dict]) -> str:
    if not rows:
        return "no posts"
    cols = ["tiktok", "youtube", "format", "diff", "theme", "slug", "title"]
    table = []
    for row in rows:
        table.append(
            {
                "tiktok": row.get("posted_at") or "-",
                "youtube": row.get("youtube_posted_at") or "-",
                "format": row.get("format") or "-",
                "diff": row.get("difficulty") or "-",
                "theme": row.get("theme") or "-",
                "slug": row.get("slug") or "-",
                "title": _short(row.get("title") or row.get("slug") or "", 40),
            }
        )
    widths = {col: len(col) for col in cols}
    for item in table:
        for col in cols:
            widths[col] = max(widths[col], len(str(item[col])))
    header = "  ".join(col.ljust(widths[col]) for col in cols)
    lines = [header]
    for item in table:
        lines.append("  ".join(str(item[col]).ljust(widths[col]) for col in cols))
    tiktok_n = sum(1 for row in rows if row.get("posted_at"))
    youtube_n = sum(1 for row in rows if row.get("youtube_posted_at"))
    unpublished_n = sum(1 for row in rows if not row.get("posted_at"))
    lines.append("")
    lines.append(
        f"{tiktok_n} on TikTok, {youtube_n} on YouTube, {unpublished_n} not posted to TikTok"
    )
    return "\n".join(lines)


def _row_from_manifest(path: Path, data: dict) -> dict:
    publish = data.get("publish") if isinstance(data.get("publish"), dict) else {}
    youtube = publish.get("youtube") if isinstance(publish.get("youtube"), dict) else {}
    return {
        "path": path,
        "slug": data.get("slug"),
        "format": data.get("format"),
        "difficulty": data.get("difficulty"),
        "theme": data.get("theme"),
        "title": data.get("title"),
        "caption": data.get("caption"),
        "posted_at": publish.get("posted_at"),
        "post_id": publish.get("post_id"),
        "url": publish.get("url"),
        "notes": publish.get("notes"),
        "youtube_id": youtube.get("video_id"),
        "youtube_posted_at": youtube.get("posted_at"),
    }


def _tiktok_posted(manifest: Path) -> bool:
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    publish = data.get("publish") if isinstance(data.get("publish"), dict) else {}
    return bool(publish.get("posted_at"))


def _as_date(value: date | str | None) -> str:
    if value is None:
        return date.today().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    parsed = date.fromisoformat(value)
    return parsed.isoformat()


def _short(text: str, width: int) -> str:
    text = " ".join(text.split())
    if len(text) <= width:
        return text
    return text[: width - 3].rstrip() + "..."


def _theme_of(manifest: Path) -> str | None:
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data.get("theme")
