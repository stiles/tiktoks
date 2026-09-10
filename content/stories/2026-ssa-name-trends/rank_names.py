from pathlib import Path

import pandas as pd

from tiktoks.io import read_yaml
from tiktoks.paths import story_data
from tiktoks.ssa_names import load_names, name_series, rank_trends

HERE = Path(__file__).resolve().parent
SLUG = HERE.name
PROCESSED_DIR = story_data(SLUG) / "processed"


def main() -> None:
    config = read_yaml(HERE / "story.yaml")
    raw_dir = story_data(config.get("raw_slug", SLUG)) / "raw"
    names = load_names(raw_dir)

    rising, falling = rank_trends(
        names,
        start_year=config["start_year"],
        end_year=config["end_year"],
        rising_min_births=config["rising_min_births"],
        rising_min_births_start=config.get("rising_min_births_start", 0),
        falling_min_births=config["falling_min_births"],
        top_n=config["top_n"],
    )

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    rising.to_csv(PROCESSED_DIR / "rising.csv", index=False)
    falling.to_csv(PROCESSED_DIR / "falling.csv", index=False)

    selected = pd.concat(
        [
            rising.assign(direction="rising"),
            falling.assign(direction="falling"),
        ],
        ignore_index=True,
    )
    series = pd.concat(
        (name_series(names, row["name"]).assign(direction=row["direction"]) for _, row in selected.iterrows()),
        ignore_index=True,
    )
    series.to_csv(PROCESSED_DIR / "name_series.csv", index=False)

    print(f"Wrote {PROCESSED_DIR / 'rising.csv'} ({len(rising)} names)")
    print(f"Wrote {PROCESSED_DIR / 'falling.csv'} ({len(falling)} names)")
    print(f"Wrote {PROCESSED_DIR / 'name_series.csv'} ({series['name'].nunique()} names)")
    print()
    print("Rising:")
    print(rising.to_string(index=False))
    print()
    print("Falling:")
    print(falling.to_string(index=False))


if __name__ == "__main__":
    main()
