"""Build a quiz batch from the country pool.

The batch YAML is still written to disk rather than rendered straight from the
pool. It is the record of what a post actually contained, it can be edited before
rendering, and `post.json` hashes it.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from tiktoks import cities, countries
from tiktoks.config import POSTS_DIR
from tiktoks.io import write_yaml

QUIZ_ROOT = POSTS_DIR / "geo-quiz"

# Which pool tier a silhouette batch draws from. Expert-tier countries are
# micro-states whose borderless outline is an indistinct speck, so the hard tier
# is as far as this variant goes. Drawing a hard or expert label from the easy
# tier gave Ireland and Italy on an expert quiz.
SILHOUETTE_POOL = {"easy": "easy", "medium": "medium", "hard": "hard", "expert": "hard"}


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
    if variant == "cities":
        return build_cities(
            tier, count, slug=slug, root=root, catalog_path=catalog_path, commit=commit
        )
    if tier == "master" and variant != "classic":
        raise ValueError("Master uses isolated outlines; omit --variant.")
    root = Path(root or QUIZ_ROOT)
    pool = countries.load(catalog_path)
    source_tier = SILHOUETTE_POOL.get(tier, tier) if variant == "silhouette" else tier
    chosen = countries.select(pool, source_tier, count)
    names = list(chosen["name"])

    slug = slug or countries.next_slug(tier, root, variant=variant)
    if variant == "globe":
        title = f"{tier.capitalize()} globe geography quiz"
        topic = "world geography globe quiz"
    elif variant == "silhouette":
        title = f"{tier.capitalize()} silhouette geography quiz"
        topic = "world geography silhouettes"
    elif variant == "progressive":
        title = f"{tier.capitalize()} progressive geography quiz"
        topic = "world geography progressive reveals"
    else:
        title = f"{tier.capitalize()} geography quiz"
        topic = "world geography"
    config = {
        "slug": slug,
        "title": title,
        "difficulty": tier,
        "topic": topic,
        "built_from": "content/countries.csv",
        "built_on": date.today().isoformat(),
        "countries": countries.to_entries(chosen),
    }
    if tier == "master":
        config["topic"] = "world geography outlines"
    if variant != "classic":
        config["variant"] = variant

    destination = root / slug / "quiz.yaml"
    if not commit:
        return destination, names

    destination.parent.mkdir(parents=True, exist_ok=True)
    write_yaml(destination, config)
    countries.save(countries.mark_rendered(pool, names), catalog_path)
    return destination, names


def build_cities(
    tier: str,
    count: int,
    *,
    slug: str | None = None,
    root: Path | None = None,
    catalog_path: Path | None = None,
    commit: bool = True,
) -> tuple[Path, list[str]]:
    """The city-pool counterpart of `build`, with its own usage counters."""
    root = Path(root or QUIZ_ROOT)
    pool = cities.load(catalog_path)
    chosen = cities.select(pool, tier, count)
    names = list(chosen["name"])

    slug = slug or countries.next_slug(tier, root, variant="cities")
    config = {
        "slug": slug,
        "title": f"{tier.capitalize()} city globe quiz",
        "difficulty": tier,
        "topic": "world geography city globe quiz",
        "variant": "cities",
        "built_from": "content/cities.csv",
        "built_on": date.today().isoformat(),
        "cities": cities.to_entries(chosen),
    }

    destination = root / slug / "quiz.yaml"
    if not commit:
        return destination, names

    destination.parent.mkdir(parents=True, exist_ok=True)
    write_yaml(destination, config)
    cities.save(countries.mark_rendered(pool, names), catalog_path)
    return destination, names
