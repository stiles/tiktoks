from pathlib import Path
from zipfile import ZipFile

import requests

from tiktoks.io import read_yaml

HERE = Path(__file__).resolve().parent
RAW_DIR = HERE / "data" / "raw"

# ssa.gov returns 403 to the default requests user agent.
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def main() -> None:
    config = read_yaml(HERE / "story.yaml")
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    zip_path = RAW_DIR / "ssa_names.zip"
    response = requests.get(config["source_url"], headers=HEADERS, timeout=60)
    response.raise_for_status()
    zip_path.write_bytes(response.content)

    with ZipFile(zip_path) as archive:
        for member in archive.namelist():
            if member.startswith("yob") and member.endswith(".txt"):
                archive.extract(member, RAW_DIR)

    print(f"Wrote SSA name files to {RAW_DIR}")


if __name__ == "__main__":
    main()
