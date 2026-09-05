"""Turn a catalog entry into map data.

`docs/guess-the-map-ideas.md` is a list of ideas that are each one query. A catalog
entry names the query; this resolves it to a frame keyed by ISO 3166-1 alpha-3 so
the renderer never sees a hand-built CSV.

Supported `fetch.kind` values:

    wikidata_members   property + value, as a 0/1 flag
    wikidata_values    property, as a number
    wikidata_query     raw SPARQL that selects ?iso3 and one value column
    worldbank          indicator code
    csv                a local file, for anything the APIs do not carry
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from tiktoks.io import read_yaml
from tiktoks.sources import wikidata, worldbank

VALUE_COLUMN = "value"


def load(catalog_path: Path | str) -> dict[str, dict]:
    """Read a catalog file and index its entries by slug."""
    config = read_yaml(catalog_path)
    entries = config.get("posts", [])
    defaults = config.get("defaults", {})
    indexed = {}
    for entry in entries:
        merged = {**defaults, **entry}
        indexed[merged["slug"]] = merged
    return indexed


def resolve(entry: dict, *, base_dir: Path | None = None) -> tuple[pd.DataFrame, str]:
    """Fetch the data an entry describes. Returns the frame and its value column."""
    spec = entry.get("fetch")
    if not spec:
        raise ValueError(f"{entry.get('slug')} has no `fetch` block")

    kind = spec["kind"]
    column = spec.get("column", VALUE_COLUMN)

    if kind == "wikidata_members":
        frame = wikidata.members(spec["property"], spec["value"], column=column)
    elif kind == "wikidata_values":
        frame = wikidata.values(spec["property"], column=column)
    elif kind == "wikidata_query":
        frame = wikidata.query(spec["sparql"])
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    elif kind == "worldbank":
        frame = worldbank.indicator(spec["indicator"], year=spec.get("year"))
        frame = frame.rename(columns={"value": column})
    elif kind == "csv":
        path = Path(base_dir or ".") / spec["path"]
        frame = pd.read_csv(path)
        frame = frame.rename(columns={spec.get("value_column", "value"): column})
    else:
        raise ValueError(f"Unknown fetch kind {kind!r}")

    if "iso3" not in frame.columns:
        raise ValueError(f"{entry.get('slug')}: fetch returned no `iso3` column")
    if spec.get("scale"):
        frame[column] = frame[column] * float(spec["scale"])

    frame = _patch(frame, spec, column)
    _verify(frame, entry, column)
    return frame, column


def _patch(frame: pd.DataFrame, spec: dict, column: str) -> pd.DataFrame:
    """Apply the entry's `include` and `exclude` corrections.

    Wikidata is not a membership registry. NATO's 32 members come back as 30
    because Denmark and the Netherlands record the statement on the kingdom rather
    than the country, and Angola still reads as OPEC after leaving in 2024. Both
    are fixed by hand here, in the open, rather than by editing a CSV.
    """
    include = [code.upper() for code in spec.get("include", [])]
    exclude = [code.upper() for code in spec.get("exclude", [])]
    if exclude:
        frame = frame[~frame["iso3"].str.upper().isin(exclude)]
    if include:
        missing = [code for code in include if code not in set(frame["iso3"].str.upper())]
        if missing:
            added = pd.DataFrame({"iso3": missing, column: 1})
            frame = pd.concat([frame, added], ignore_index=True)
    return frame


def _verify(frame: pd.DataFrame, entry: dict, column: str) -> None:
    """Fail the render when a query returns an unexpected number of countries.

    A map with the wrong countries shaded is worse than no map. The count is the
    cheapest check that catches a changed property, a wrong QID or a silent
    upstream edit.
    """
    expect = entry.get("expect") or {}
    count = len(frame)
    if "count" in expect and count != expect["count"]:
        raise ValueError(
            f"{entry['slug']}: expected {expect['count']} countries, got {count}. "
            "Check the query, or update `expect.count` if the world changed."
        )
    minimum = expect.get("min_countries")
    if minimum and count < minimum:
        raise ValueError(f"{entry['slug']}: only {count} countries, expected at least {minimum}")
