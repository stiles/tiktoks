"""Build a quiz batch from the country pool.

The batch YAML is still written to disk rather than rendered straight from the
pool. It is the record of what a post actually contained, it can be edited before
rendering, and `post.json` hashes it.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from tiktoks import countries
from tiktoks.config import POSTS_DIR
from tiktoks.io import write_yaml

QUIZ_ROOT = POSTS_DIR / "geo-quiz"


def build(
    tier: str,
    count: int,
    *,
    slug: str | None = None,
    variant: str = "classic",
    root: Path | None = None,
    catalog_path: Path | None = None,
    commit: bool = True,
) -> tuple[Path, list[str]]:
    """Pick `count` countries, write a batch config and record the usage.

    Returns the config path and the names chosen. With `commit=False` nothing is
    written, which is what `--dry-run` uses.
    """
    root = Path(root or QUIZ_ROOT)
    pool = countries.load(catalog_path)
    by_tier = variant == "classic"
    chosen = countries.select(pool, tier if by_tier else None, count, by_tier=by_tier)
    names = list(chosen["name"])

    slug = slug or countries.next_slug(tier, root, variant=variant)
    title = (
        f"{tier.capitalize()} silhouette geography quiz"
        if variant == "silhouette"
        else f"{tier.capitalize()} geography quiz"
    )
    config = {
        "slug": slug,
        "title": title,
        "difficulty": tier,
        "topic": "world geography silhouettes" if variant == "silhouette" else "world geography",
        "built_from": "content/countries.csv",
        "built_on": date.today().isoformat(),
        "countries": countries.to_entries(chosen),
    }
    if variant != "classic":
        config["variant"] = variant

    destination = root / slug / "quiz.yaml"
    if not commit:
        return destination, names

    destination.parent.mkdir(parents=True, exist_ok=True)
    write_yaml(destination, config)
    countries.save(countries.mark_rendered(pool, names), catalog_path)
    return destination, names
