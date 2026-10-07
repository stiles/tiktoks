"""The city pool behind city globe quizzes.

Works like the country pool in `countries.py`: a hand-tiered CSV, least-recently-
used selection and usage written back when a batch is built. The tier is a guess
at how hard the dot is to place, not how famous the city is. Anywhere in the
United States is easy, because any dot on that landmass gives the country; Lahore
is hard, because the dot sits a few miles from India.

Coordinates come from Esri's World Cities layer and are stored in the pool, so a
render never needs the network. Display names and countries are ours: Esri spells
some names oddly (T'Bilisi, Ndjamena) and files Taipei under China.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from tiktoks import countries
from tiktoks.config import CITY_POOL_PATH, REFERENCE_DIR, WORLD_CITIES_URL

TIERS = ("easy", "medium", "hard", "expert")

COLUMNS = [
    "name",
    "country",
    "tier",
    "fact",
    "source",
    "hook",
    "lon",
    "lat",
    "esri_name",
    "esri_country",
    "times_used",
    "last_rendered",
    "notes",
]

ESRI_CACHE = REFERENCE_DIR / "esri_world_cities.geojson"

# How far a stored coordinate can drift from Esri's before validation flags it.
MAX_DRIFT_KM = 25


def load(path: Path | str | None = None) -> pd.DataFrame:
    path = Path(path or CITY_POOL_PATH)
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing")
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = [column for column in COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"{path} is missing columns: {', '.join(missing)}")
    frame["times_used"] = pd.to_numeric(frame["times_used"], errors="coerce").fillna(0).astype(int)
    return frame


def save(frame: pd.DataFrame, path: Path | str | None = None) -> Path:
    path = Path(path or CITY_POOL_PATH)
    frame[COLUMNS].to_csv(path, index=False)
    return path


def select(frame: pd.DataFrame, tier: str, count: int) -> pd.DataFrame:
    if tier not in TIERS:
        raise ValueError(f"Unknown city tier {tier!r}. Options: {', '.join(TIERS)}")
    unlocated = frame.loc[(frame["tier"] == tier) & ((frame["lon"] == "") | (frame["lat"] == ""))]
    if not unlocated.empty:
        names = ", ".join(unlocated["name"])
        raise ValueError(f"No coordinates for {names}. Run `tiktoks quiz locate-cities`.")
    return countries.select(frame, tier, count)


def to_entries(rows: pd.DataFrame) -> list[dict]:
    """Pool rows as city quiz config entries, dropping blank overrides."""
    entries = []
    for _, row in rows.iterrows():
        entry: dict = {
            "name": row["name"],
            "country": row["country"],
            "lon": round(float(row["lon"]), 4),
            "lat": round(float(row["lat"]), 4),
            "fact": row["fact"],
        }
        if row["hook"]:
            entry["hook"] = row["hook"]
        entries.append(entry)
    return entries


def status(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for tier in TIERS:
        pool = frame[frame["tier"] == tier]
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


# Esri


def esri_cities(refresh: bool = False) -> gpd.GeoDataFrame:
    """Esri's World Cities layer, downloaded once and cached under data/reference."""
    if ESRI_CACHE.exists() and not refresh:
        return gpd.read_file(ESRI_CACHE)
    import ezesri

    frame = ezesri.extract_layer(WORLD_CITIES_URL)
    ESRI_CACHE.parent.mkdir(parents=True, exist_ok=True)
    frame.to_file(ESRI_CACHE, driver="GeoJSON")
    return frame


def esri_match(layer: gpd.GeoDataFrame, row: pd.Series) -> gpd.GeoDataFrame:
    """Esri features for a pool row, narrowed by country when a name repeats."""
    matched = layer.loc[layer["CITY_NAME"] == (row["esri_name"] or row["name"])]
    if len(matched) > 1:
        matched = matched.loc[matched["CNTRY_NAME"] == (row["esri_country"] or row["country"])]
    return matched


def locate(frame: pd.DataFrame, layer: gpd.GeoDataFrame | None = None) -> list[str]:
    """Fill blank coordinates from Esri. Returns rows that could not be resolved."""
    layer = esri_cities() if layer is None else layer
    problems = []
    for index, row in frame.iterrows():
        if row["lon"] and row["lat"]:
            continue
        matched = esri_match(layer, row)
        if len(matched) != 1:
            problems.append(f"{row['name']}: {len(matched)} Esri matches")
            continue
        point = matched.geometry.iloc[0]
        frame.loc[index, ["lon", "lat"]] = [f"{point.x:.4f}", f"{point.y:.4f}"]
        if not row["source"]:
            frame.loc[index, "source"] = "Esri World Cities"
    return problems


def validate(frame: pd.DataFrame, layer: gpd.GeoDataFrame | None = None) -> list[str]:
    """Duplicate names, unknown tiers, and coordinates that disagree with Esri."""
    layer = esri_cities() if layer is None else layer
    problems = [
        f"{name}: appears more than once; usage tracking keys on the name"
        for name in frame.loc[frame["name"].duplicated(), "name"]
    ]
    for _, row in frame.iterrows():
        if row["tier"] not in TIERS:
            problems.append(f"{row['name']}: unknown tier {row['tier']!r}")
        if not (row["lon"] and row["lat"]):
            problems.append(f"{row['name']}: no coordinates")
            continue
        matched = esri_match(layer, row)
        if len(matched) != 1:
            problems.append(f"{row['name']}: {len(matched)} Esri matches")
            continue
        point = matched.geometry.iloc[0]
        drift = _km(float(row["lon"]), float(row["lat"]), point.x, point.y)
        if drift > MAX_DRIFT_KM:
            problems.append(f"{row['name']}: {drift:.0f} km from Esri's point")
    return problems


def _km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    from tiktoks.maps import angular_distance

    return float(np.radians(angular_distance(lon1, lat1, lon2, lat2)) * 6371)
