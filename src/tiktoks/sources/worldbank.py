"""World Bank indicators, returned as a frame keyed by ISO 3166-1 alpha-3.

The API returns aggregates (world, income groups, regions) alongside countries.
Those are dropped here; a choropleth of "Sub-Saharan Africa" as a single row would
silently blow up the quantile breaks.
"""

from __future__ import annotations

import json
import time

import pandas as pd
import requests

from tiktoks.config import REFERENCE_DIR

BASE = "https://api.worldbank.org/v2"
USER_AGENT = "tiktoks/0.1 (personal data-journalism project)"
CACHE_DIR = REFERENCE_DIR / "worldbank"
CACHE_DAYS = 30

# The API returns intermittent 502s under no particular load, which would fail a
# scheduled render for no reason.
RETRIES = 6
BACKOFF = 5.0


def _get(url: str, params: dict) -> requests.Response:
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            response = requests.get(
                url, params=params, headers={"User-Agent": USER_AGENT}, timeout=90
            )
            response.raise_for_status()
            return response
        except (requests.HTTPError, requests.ConnectionError, requests.Timeout) as error:
            last = error
            if attempt < RETRIES - 1:
                time.sleep(BACKOFF * (attempt + 1))
    raise RuntimeError(f"World Bank request failed after {RETRIES} tries: {last}")


def indicator(code: str, *, year: int | None = None, mrv: int = 5) -> pd.DataFrame:
    """One indicator per country, taking the most recent non-null value.

    `mrv` is how many recent years to consider before giving up on a country, which
    matters because World Bank coverage lags unevenly by country.
    """
    params = {"format": "json", "per_page": 20000}
    if year:
        params["date"] = str(year)
    else:
        params["mrv"] = mrv

    # Cache on disk. The API 502s intermittently, and a scheduled render should not
    # depend on catching it in a good mood.
    cache = CACHE_DIR / f"{code}-{year or f'mrv{mrv}'}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_DAYS * 86400:
        payload = json.loads(cache.read_text(encoding="utf-8"))
    else:
        payload = _get(f"{BASE}/country/all/indicator/{code}", params).json()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(payload), encoding="utf-8")
    if len(payload) < 2 or not payload[1]:
        raise ValueError(f"World Bank returned no rows for {code}")

    frame = pd.DataFrame(
        {
            "iso3": row["countryiso3code"],
            "name": row["country"]["value"],
            "year": int(row["date"]),
            "value": row["value"],
            "region_id": (row.get("country", {}) or {}).get("id"),
        }
        for row in payload[1]
    )
    # Aggregates come back with a blank or non-three-letter ISO3 field.
    frame = frame[frame["iso3"].str.len() == 3]
    frame = frame.dropna(subset=["value"])
    frame = frame.sort_values("year").groupby("iso3", as_index=False).last()
    return frame[["iso3", "name", "year", "value"]]


INDICATORS = {
    "gdp_per_capita": "NY.GDP.PCAP.CD",
    "population": "SP.POP.TOTL",
    "life_expectancy": "SP.DYN.LE00.IN",
    "internet_use": "IT.NET.USER.ZS",
    "urban_share": "SP.URB.TOTL.IN.ZS",
    "co2_per_capita": "EN.GHG.CO2.PC.CE.AR5",
    "forest_share": "AG.LND.FRST.ZS",
}
