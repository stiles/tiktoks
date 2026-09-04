from pathlib import Path

import pandas as pd

from tiktoks.io import read_yaml

HERE = Path(__file__).resolve().parent
RAW_DIR = HERE / "data" / "raw"
PROCESSED_DIR = HERE / "data" / "processed"


def read_year_file(path: Path) -> pd.DataFrame:
    year = int(path.stem.replace("yob", ""))
    df = pd.read_csv(path, names=["name", "sex", "births"])
    df["year"] = year
    return df


def main() -> None:
    config = read_yaml(HERE / "story.yaml")
    target = config["name"].casefold()
    files = sorted(RAW_DIR.glob("yob*.txt"))
    if not files:
        raise FileNotFoundError("Run fetch.py before process.py")

    names = pd.concat((read_year_file(path) for path in files), ignore_index=True)
    yearly_totals = names.groupby("year", as_index=False)["births"].sum()
    selected = (
        names[names["name"].str.casefold() == target]
        .groupby("year", as_index=False)["births"]
        .sum()
        .merge(yearly_totals, on="year", suffixes=("", "_all"))
    )
    selected["share_per_100k"] = selected["births"] / selected["births_all"] * 100_000

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    selected.to_csv(PROCESSED_DIR / "name_series.csv", index=False)
    print(f"Wrote {PROCESSED_DIR / 'name_series.csv'}")


if __name__ == "__main__":
    main()
