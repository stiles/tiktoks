"""Tie polygon names to ISO 3166-1 alpha-3 codes and Wikidata QIDs.

The CNN country polygons carry `sovereignt`, `name` and `name_long` and no code,
so a Wikidata or World Bank result has nothing to join to. This builds
`data/reference/country_crosswalk.csv` once. Rerun it when the boundary file
changes.

Matching runs label, then alias, then the overrides below. Anything still
unmatched is printed so it can be added by hand rather than dropped quietly.
"""

import re
import sys

import pandas as pd

from tiktoks.config import CROSSWALK_PATH
from tiktoks.maps import world_countries
from tiktoks.sources import wikidata

# Cases where the polygon name and every Wikidata English label and alias differ,
# or where the alias list is ambiguous enough to match the wrong entity.
OVERRIDES = {
    "united states of america": "USA",
    "united kingdom": "GBR",
    "democratic republic of the congo": "COD",
    "republic of the congo": "COG",
    "republic of serbia": "SRB",
    "czechia": "CZE",
    "ivory coast": "CIV",
    "guinea bissau": "GNB",
    "east timor": "TLS",
    "macedonia": "MKD",
    "north macedonia": "MKD",
    "swaziland": "SWZ",
    "eswatini": "SWZ",
    "cape verde": "CPV",
    "burma": "MMR",
    "myanmar": "MMR",
    "south korea": "KOR",
    "north korea": "PRK",
    "laos": "LAO",
    "russia": "RUS",
    "vatican": "VAT",
    "brunei": "BRN",
    "the bahamas": "BHS",
    "the gambia": "GMB",
    "united republic of tanzania": "TZA",
    "syria": "SYR",
    "iran": "IRN",
    "vietnam": "VNM",
    "moldova": "MDA",
    "bolivia": "BOL",
    "venezuela": "VEN",
    "sao tome and principe": "STP",
    "saint vincent and the grenadines": "VCT",
    "federated states of micronesia": "FSM",
    "hong kong s.a.r.": "HKG",
    "macao s.a.r": "MAC",
    "falkland islands": "FLK",
    "french southern and antarctic lands": "ATF",
    "heard island and mcdonald islands": "HMD",
    "saint helena": "SHN",
    "curaçao": "CUW",
    "curacao": "CUW",
    "sint maarten": "SXM",
    "saint martin": "MAF",
    "saint barthelemy": "BLM",
    "pitcairn islands": "PCN",
    "wallis and futuna": "WLF",
    "united states virgin islands": "VIR",
    "british virgin islands": "VGB",
    "turks and caicos islands": "TCA",
    "cayman islands": "CYM",
    "faroe islands": "FRO",
    "aland": "ALA",
    "åland": "ALA",
    "isle of man": "IMN",
    "south georgia and the islands": "SGS",
    "british indian ocean territory": "IOT",
    "northern mariana islands": "MNP",
    "cook islands": "COK",
    "marshall islands": "MHL",
    "solomon islands": "SLB",
    "antarctica": None,
    # Natural Earth abbreviates in the `name` column.
    "china": "CHN",
    "cte divoire": "CIV",
    "dem rep korea": "PRK",
    "heard i and mcdonald is": "HMD",
    "macao": "MAC",
    "stbarthlemy": "BLM",
    "so tom and principe": "STP",
}

# Places with no ISO 3166-1 code. They are real polygons and should stay on the
# map, but they can never carry a code, so the crosswalk records them as such.
NO_CODE = {
    "northern cyprus",
    "somaliland",
    "kosovo",
    "western sahara",
    "indian ocean territories",
    "ashmore and cartier islands",
    "siachen glacier",
    "baikonur cosmodrome",
    "bajo nuevo bank",
    "serranilla bank",
    "scarborough reef",
    "spratly islands",
    "paracel islands",
    "clipperton island",
    "coral sea islands",
    "cyprus no mans area",
    "united nations buffer zone in cyprus",
    "dhekelia sovereign base area",
    "akrotiri sovereign base area",
    "brazilian island",
    "us naval base guantanamo bay",
    "antarctica",
    "ashmore and cartier is",
    "golan heights",
    "indian ocean ter",
    "n cyprus",
}


def normalize(text: str) -> str:
    text = str(text).casefold().strip()
    text = text.replace("&", "and")
    return re.sub(r"[^a-z0-9 ]+", "", text).strip()


def main() -> int:
    polygons = world_countries()
    print(f"{len(polygons)} polygons")

    wd = wikidata.countries_with_codes()
    print(f"{len(wd)} Wikidata rows with an ISO3 code")

    # Build a lookup from every English label and alias to (iso3, qid).
    lookup: dict[str, tuple[str, str]] = {}
    for _, row in wd.iterrows():
        qid = str(row["item"]).rsplit("/", 1)[-1]
        entry = (row["iso3"], qid)
        for candidate in (row.get("itemLabel"), row.get("alias")):
            if not candidate or pd.isna(candidate):
                continue
            key = normalize(candidate)
            # Labels win over aliases; an alias never overwrites an existing key.
            if key and key not in lookup:
                lookup[key] = entry
    by_code = {code: (code, qid) for code, qid in lookup.values()}

    records = []
    unmatched = []
    for _, row in polygons.iterrows():
        name = row["name"]
        key = normalize(name)
        hit = None
        how = None

        if key in NO_CODE:
            how = "no code"
        elif key in OVERRIDES:
            code = OVERRIDES[key]
            hit = by_code.get(code) if code else None
            how = "override"
        else:
            for column, source in (("name", name), ("name_long", row["name_long"])):
                found = lookup.get(normalize(source))
                if found:
                    hit, how = found, column
                    break

        if hit is None and how != "no code":
            unmatched.append(name)

        records.append(
            {
                "name": name,
                "name_long": row["name_long"],
                "sovereignt": row["sovereignt"],
                "iso3": hit[0] if hit else "",
                "qid": hit[1] if hit else "",
                "matched_on": how or "",
            }
        )

    frame = pd.DataFrame(records).sort_values("name")
    CROSSWALK_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(CROSSWALK_PATH, index=False)

    coded = (frame["iso3"] != "").sum()
    print(f"{coded} of {len(frame)} polygons carry an ISO3 code -> {CROSSWALK_PATH}")
    if unmatched:
        print(f"\n{len(unmatched)} unmatched, add to OVERRIDES or NO_CODE:")
        for name in sorted(unmatched):
            print(f"  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
