from pathlib import Path
from zipfile import ZipFile

import requests

from tiktoks.io import read_yaml
from tiktoks.paths import story_data

HERE = Path(__file__).resolve().parent
SLUG = HERE.name
RAW_DIR = story_data(SLUG) / "raw"

# ssa.gov returns 403 to the default requests user agent.
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def main() -> None:
    config = read_yaml(HERE / "story.yaml")
    state = config["state"].upper()
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    zip_path = RAW_DIR / "ssa_names_by_state.zip"
    response = requests.get(config["source_url"], headers=HEADERS, timeout=120)
    response.raise_for_status()
    zip_path.write_bytes(response.content)

    member = f"{state}.TXT"
    with ZipFile(zip_path) as archive:
        if member not in archive.namelist():
            raise FileNotFoundError(f"{member} not found in SSA state archive")
        archive.extract(member, RAW_DIR)

    print(f"Wrote {RAW_DIR / member}")


if __name__ == "__main__":
    main()
