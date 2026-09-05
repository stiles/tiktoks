"""Wikidata SPARQL, returned as a frame keyed by ISO 3166-1 alpha-3.

Wikidata asks for a descriptive User-Agent and rate-limits anonymous traffic, so
results are cached on disk. A catalog entry that has not changed does not refetch.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pandas as pd
import requests

from tiktoks.config import REFERENCE_DIR

ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "tiktoks/0.1 (personal data-journalism project; contact via GitHub)"
CACHE_DIR = REFERENCE_DIR / "wikidata"
CACHE_DAYS = 30

# ISO 3166-1 alpha-3 is P298. Every query here keys on it so results join to the
# country crosswalk rather than to a label.
ISO3 = "wdt:P298"


def query(sparql: str, *, cache: bool = True, timeout: int = 90) -> pd.DataFrame:
    """Run a SPARQL query and return the bindings as a flat frame."""
    key = hashlib.sha256(sparql.encode("utf-8")).hexdigest()[:16]
    path = CACHE_DIR / f"{key}.json"
    if cache and path.exists() and time.time() - path.stat().st_mtime < CACHE_DAYS * 86400:
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        response = requests.get(
            ENDPOINT,
            params={"query": sparql, "format": "json"},
            headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if cache:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")

    rows = [
        {name: binding[name]["value"] for name in binding}
        for binding in payload["results"]["bindings"]
    ]
    return pd.DataFrame(rows)


def members(
    property_id: str, value_qid: str, *, column: str = "member", current_only: bool = True
) -> pd.DataFrame:
    """Countries where `property_id` points at `value_qid`, as a 0/1 flag.

    Covers the binary half of the guess-the-map backlog: NATO membership (P463 /
    Q7184), euro as currency (P38 / Q4916), driving side (P1622 / Q11920728).

    `current_only` reads the statement rather than the truthy value so a membership
    that has ended (P582) can be dropped, and skips countries that no longer exist
    (P576). Without it a euro map includes Serbia and Montenegro.
    """
    ended = "FILTER NOT EXISTS { ?statement pq:P582 ?end }" if current_only else ""
    gone = "FILTER NOT EXISTS { ?country wdt:P576 ?dissolved }" if current_only else ""
    frame = query(f"""
        SELECT DISTINCT ?iso3 WHERE {{
          ?country {ISO3} ?iso3 .
          ?country p:{property_id} ?statement .
          ?statement ps:{property_id} wd:{value_qid} .
          {ended}
          {gone}
        }}
    """)
    if frame.empty:
        return pd.DataFrame(columns=["iso3", column])
    frame[column] = 1
    return frame[["iso3", column]].drop_duplicates("iso3")


def values(property_id: str, *, column: str = "value") -> pd.DataFrame:
    """The most recent value of a numeric property, per country."""
    frame = query(f"""
        SELECT ?iso3 (MAX(?raw) AS ?{column}) WHERE {{
          ?country {ISO3} ?iso3 .
          ?country wdt:{property_id} ?raw .
        }}
        GROUP BY ?iso3
    """)
    if frame.empty:
        return pd.DataFrame(columns=["iso3", column])
    frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=[column])


def countries_with_codes() -> pd.DataFrame:
    """Every entity carrying an ISO 3166-1 alpha-3 code, with labels and aliases.

    Used once, by `scripts/build_crosswalk.py`, to tie polygon names to codes.
    """
    return query("""
        SELECT ?item ?itemLabel ?iso3 ?alias WHERE {
          ?item wdt:P298 ?iso3 .
          OPTIONAL { ?item skos:altLabel ?alias . FILTER(LANG(?alias) = "en") }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
    """)


def cache_path() -> Path:
    return CACHE_DIR
