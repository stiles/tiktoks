from pathlib import Path

import pandas as pd

from tiktoks.io import read_yaml
from tiktoks.paths import story_data
from tiktoks.ssa_names import load_state_names, state_name_series, top_names_by_sex

HERE = Path(__file__).resolve().parent
SLUG = HERE.name
RAW_DIR = story_data(SLUG) / "raw"
PROCESSED_DIR = story_data(SLUG) / "processed"


def main() -> None:
    config = read_yaml(HERE / "story.yaml")
    state = config["state"]
    year = config["year"]
    names = load_state_names(RAW_DIR, state)
    girls, boys = top_names_by_sex(names, year, config["top_n"])

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    girls.to_csv(PROCESSED_DIR / "girls.csv", index=False)
    boys.to_csv(PROCESSED_DIR / "boys.csv", index=False)

    selected = pd.concat(
        [
            girls.assign(direction="girls"),
            boys.assign(direction="boys"),
        ],
        ignore_index=True,
    )
    series = pd.concat(
        (
            state_name_series(names, row["name"], row["sex"]).assign(
                direction=row["direction"],
                rank=row["rank"],
            )
            for _, row in selected.iterrows()
        ),
        ignore_index=True,
    )
    series.to_csv(PROCESSED_DIR / "name_series.csv", index=False)

    print(f"Wrote {PROCESSED_DIR / 'girls.csv'} ({len(girls)} names)")
    print(f"Wrote {PROCESSED_DIR / 'boys.csv'} ({len(boys)} names)")
    print(f"Wrote {PROCESSED_DIR / 'name_series.csv'} ({series['name'].nunique()} names)")
    print()
    print("Girls:")
    print(girls.to_string(index=False))
    print()
    print("Boys:")
    print(boys.to_string(index=False))


if __name__ == "__main__":
    main()
