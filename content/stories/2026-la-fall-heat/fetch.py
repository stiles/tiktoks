"""Daily highs and lows for each station, plus LAX's daily normals for the story year.

ACIS (data.rcc-acis.org) serves the NOAA station records behind the Western
Regional Climate Center tables, as JSON.
"""

from pathlib import Path

import pandas as pd
import requests

from tiktoks.io import read_yaml
from tiktoks.paths import ensure_dir, story_data

HERE = Path(__file__).resolve().parent
ACIS = "https://data.rcc-acis.org/StnData"


def acis(params: dict) -> list:
    response = requests.post(ACIS, json=params, timeout=120)
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"ACIS: {payload['error']}")
    return payload["data"]


def main() -> None:
    config = read_yaml(HERE / "story.yaml")
    raw = ensure_dir(story_data(config["slug"]) / "raw")

    for station in config["stations"].values():
        rows = acis(
            {"sid": station["sid"], "sdate": "por", "edate": "por", "elems": ["maxt", "mint"]}
        )
        path = raw / f"daily_{station['sid']}.csv"
        pd.DataFrame(rows, columns=["date", "hi", "lo"]).to_csv(path, index=False)
        print(f"{station['name']}: {len(rows):,} days -> {path}")

    lax = config["stations"]["lax"]["sid"]
    year = config["year"]
    rows = acis(
        {
            "sid": lax,
            "sdate": f"{year}-01-01",
            "edate": f"{year}-12-31",
            "elems": [{"name": "maxt", "normal": "1"}, {"name": "mint", "normal": "1"}],
        }
    )
    path = raw / f"normals_{lax}.csv"
    pd.DataFrame(rows, columns=["date", "normal_hi", "normal_lo"]).to_csv(path, index=False)
    print(f"LAX daily normals -> {path}")


if __name__ == "__main__":
    main()
