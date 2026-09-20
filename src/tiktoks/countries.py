"""The country pool behind geography quiz batches.

`docs/geo-quiz-rollout.md` held 40 countries as a markdown list and the batch
config repeated ten of them. That works for batch 001 and breaks by batch 020,
when the question becomes which countries have already run. The pool lives in
`content/countries.csv` instead, and a batch is a query against it.

Selection is least-recently-used: never-used countries first, then the ones that
ran longest ago. Rendering a batch writes the usage back, so the next call picks
up where this one left off.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from tiktoks.config import COUNTRY_POOL_PATH

CATALOG_PATH = COUNTRY_POOL_PATH
TIERS = ("easy", "medium", "hard", "expert", "master")


def tier_pool(frame: pd.DataFrame, tier: str) -> pd.DataFrame:
    """Master shares expert candidates and usage; its challenge is the missing context."""
    return frame[frame["tier"] == ("expert" if tier == "master" else tier)]


COLUMNS = [
    "name",
    "match_name",
    "tier",
    "fact",
    "source",
    "hook",
    "center_lon",
    "center_lat",
    "zoom",
    "context",
    "times_used",
    "last_rendered",
    "notes",
]


def load(path: Path | str | None = None) -> pd.DataFrame:
    path = Path(path or CATALOG_PATH)
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing")
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = [column for column in COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"{path} is missing columns: {', '.join(missing)}")
    frame["times_used"] = pd.to_numeric(frame["times_used"], errors="coerce").fillna(0).astype(int)
    return frame


def save(frame: pd.DataFrame, path: Path | str | None = None) -> Path:
    path = Path(path or CATALOG_PATH)
    frame[COLUMNS].to_csv(path, index=False)
    return path


def select(
    frame: pd.DataFrame, tier: str | None, count: int, *, by_tier: bool = True
) -> pd.DataFrame:
    """The `count` least-recently-used countries in a tier, or across the whole pool.

    Recency sorts ahead of the use count, because repeating a country posted last
    week is worse than repeating one posted twice a year ago. An empty
    `last_rendered` sorts first, so never-used countries go before used ones.
    """
    if by_tier:
        if tier not in TIERS:
            raise ValueError(f"Unknown tier {tier!r}. Options: {', '.join(TIERS)}")
        pool = tier_pool(frame, tier)
        if pool.empty:
            raise ValueError(f"No countries in the {tier} tier")
        if len(pool) < count:
            raise ValueError(f"Asked for {count} {tier} countries, the pool has {len(pool)}")
    else:
        pool = frame
        if len(pool) < count:
            raise ValueError(f"Asked for {count} countries, the pool has {len(pool)}")

    # Legacy rows hold dates; new rows hold UTC timestamps. Parse both so offsets
    # and date-only records compare chronologically, with never-used rows first.
    ordered = pool.assign(
        _recency=pd.to_datetime(pool["last_rendered"], format="mixed", utc=True)
    ).sort_values(["_recency", "times_used", "name"], kind="stable", na_position="first")
    return ordered.head(count).drop(columns="_recency")


def mark_rendered(
    frame: pd.DataFrame, names: list[str], when: date | datetime | None = None
) -> pd.DataFrame:
    """Bump the usage counters for the countries that just went into a batch."""
    moment = when or datetime.now(UTC)
    stamp = (
        moment.astimezone(UTC).isoformat() if isinstance(moment, datetime) else moment.isoformat()
    )
    chosen = frame["name"].isin(names)
    frame.loc[chosen, "times_used"] = frame.loc[chosen, "times_used"] + 1
    frame.loc[chosen, "last_rendered"] = stamp
    return frame


def to_entries(rows: pd.DataFrame) -> list[dict]:
    """Catalog rows as geo-quiz config entries, dropping blank overrides."""
    entries = []
    for _, row in rows.iterrows():
        entry: dict = {"name": row["name"], "fact": row["fact"]}
        if row["match_name"]:
            entry["match_name"] = row["match_name"]
        if row["hook"]:
            entry["hook"] = row["hook"]
        if row["context"]:
            entry["context"] = row["context"]
        if row["zoom"]:
            entry["zoom"] = float(row["zoom"])
        if row["center_lon"] and row["center_lat"]:
            entry["center"] = [float(row["center_lon"]), float(row["center_lat"])]
        entries.append(entry)
    return entries


def next_slug(tier: str, root: Path, *, variant: str = "classic") -> str:
    """The next unused batch directory for a tier and variant."""
    prefix = f"geo-{tier}-" if variant == "classic" else f"geo-{variant}-{tier}-"
    existing = (
        {path.name for path in Path(root).glob(f"{prefix}*")} if Path(root).exists() else set()
    )
    number = 1
    while f"{prefix}{number:03d}" in existing:
        number += 1
    return f"{prefix}{number:03d}"


def status(frame: pd.DataFrame) -> pd.DataFrame:
    """Per-tier pool depth, so it is obvious when a tier needs more countries."""
    rows = []
    for tier in TIERS:
        pool = tier_pool(frame, tier)
        rows.append(
            {
                "tier": tier,
                "total": len(pool),
                "unused": int((pool["times_used"] == 0).sum()),
                "used": int((pool["times_used"] > 0).sum()),
                "last_rendered": max(
                    [value for value in pool["last_rendered"] if value], default=""
                ),
            }
        )
    return pd.DataFrame(rows)


def validate(frame: pd.DataFrame) -> list[str]:
    """Names that do not resolve to exactly one polygon.

    Worth running before a batch, because a bad name fails halfway through a
    render rather than up front. Eswatini is the standing example: the boundary
    file still calls it Swaziland.
    """
    from tiktoks.maps import country_match, quiz_countries

    countries = quiz_countries()
    problems = []
    for _, row in frame.iterrows():
        lookup = row["match_name"] or row["name"]
        try:
            matched = country_match(countries, [lookup])
        except ValueError:
            problems.append(f"{row['name']}: no polygon matches {lookup!r}")
            continue
        if len(matched) != 1:
            problems.append(f"{row['name']}: {lookup!r} matches {len(matched)} polygons")
    return problems
