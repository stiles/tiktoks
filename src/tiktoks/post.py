"""A post is an ordered run of slides plus the metadata needed to find it again.

Rendering writes `post.json` next to the PNGs. That file is what lets a view count
pulled three weeks later be attributed to a format, a difficulty and a batch.
`docs/roadmap.md` calls this the join problem and proposes a CSV filled in by hand
at publish time; everything except the TikTok post ID is known at render time.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from tiktoks.config import CANVAS_SIZE, ROOT
from tiktoks.export import contact_sheet, validate_export
from tiktoks.paths import ensure_dir
from tiktoks.slides import Slide
from tiktoks.style import Theme


class LayoutError(RuntimeError):
    """Raised when a slide puts content under TikTok's own interface."""


@dataclass
class SlideRecord:
    index: int
    file: str
    kind: str
    alt: str
    title: str | None = None


@dataclass
class Post:
    slug: str
    format: str
    theme: Theme
    output_dir: Path
    difficulty: str | None = None
    topic: str | None = None
    title: str | None = None
    caption: str | None = None
    hashtags: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    config_path: Path | None = None
    strict: bool = True

    slides: list[SlideRecord] = field(default_factory=list)
    paths: list[Path] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def add(self, slide: Slide, *, kind: str, alt: str, title: str | None = None) -> Path:
        """Check, save and record one slide. Order of calls is slide order."""
        index = len(self.slides) + 1
        # The layout check needs a live renderer, so it has to run before save()
        # closes the figure.
        for problem in slide.check_layout():
            self.problems.append(f"{self.slug} slide {index:02d} ({kind}): {problem}")

        name = f"{self.slug}-{index:02d}-{kind}.png"
        path = slide.save(Path(self.output_dir) / name)
        validate_export(path)

        self.slides.append(SlideRecord(index=index, file=name, kind=kind, alt=alt, title=title))
        self.paths.append(path)
        return path

    def finish(self, *, sheet: bool = True) -> Path:
        """Write the manifest and, optionally, a contact sheet for thumbnail review."""
        directory = ensure_dir(self.output_dir)
        if sheet and self.paths:
            contact_sheet(self.paths, directory / f"{self.slug}-contact-sheet.png")

        manifest = directory / "post.json"
        manifest.write_text(json.dumps(self.manifest(), indent=2) + "\n", encoding="utf-8")

        if self.problems and self.strict:
            raise LayoutError(
                f"{len(self.problems)} layout problem(s):\n  " + "\n  ".join(self.problems)
            )
        return manifest

    def manifest(self) -> dict:
        return {
            "slug": self.slug,
            "format": self.format,
            "theme": self.theme.name,
            "difficulty": self.difficulty,
            "topic": self.topic,
            "title": self.title,
            "caption": self.caption or self.default_caption(),
            "hashtags": self.hashtags,
            "sources": self.sources,
            "canvas": list(CANVAS_SIZE),
            "slide_count": len(self.slides),
            "slides": [asdict(record) for record in self.slides],
            "rendered_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "git_sha": git_sha(),
            "config": _relative(self.config_path),
            "config_hash": file_hash(self.config_path),
            "layout_problems": self.problems,
            # Filled in by hand after posting. This is the only part that cannot be
            # known at render time.
            "publish": {"post_id": None, "url": None, "posted_at": None},
        }

    def default_caption(self) -> str:
        parts = [self.title or self.slug]
        if self.difficulty:
            parts.append(f"Difficulty: {self.difficulty}.")
        if self.hashtags:
            parts.append(" ".join(f"#{tag.lstrip('#')}" for tag in self.hashtags))
        return " ".join(parts)


def _relative(path: Path | None) -> str | None:
    """Repo-relative, so a manifest reads the same on any machine."""
    if not path:
        return None
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def git_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, check=True
        )
    except (subprocess.SubprocessError, OSError):
        return None
    return result.stdout.strip() or None


def file_hash(path: Path | None) -> str | None:
    if not path or not Path(path).exists():
        return None
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
