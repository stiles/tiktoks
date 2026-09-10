from pathlib import Path

from tiktoks.io import read_yaml
from tiktoks.paths import story_data
from tiktoks.ssa_names import load_names, name_series

HERE = Path(__file__).resolve().parent
SLUG = HERE.name
RAW_DIR = story_data(SLUG) / "raw"
PROCESSED_DIR = story_data(SLUG) / "processed"


def main() -> None:
    config = read_yaml(HERE / "story.yaml")
    names = load_names(RAW_DIR)
    selected = name_series(names, config["name"])

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    selected.to_csv(PROCESSED_DIR / "name_series.csv", index=False)
    print(f"Wrote {PROCESSED_DIR / 'name_series.csv'}")


if __name__ == "__main__":
    main()
