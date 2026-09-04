from pathlib import Path

CANVAS_SIZE = (1080, 1920)
SAFE_AREA = {
    "left": 96,
    "right": 96,
    "top": 150,
    "bottom": 180,
}

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
REFERENCE_DIR = DATA_DIR / "reference"
OUTPUT_DIR = ROOT / "output"

GIS_URLS = {
    "countries": "https://ix.cnn.io/data/gis/cnn-country-polys-50m.geojson",
    "country_lines": "https://ix.cnn.io/data/gis/cnn-country-lines-50m.geojson",
    "disputed_lines": "https://ix.cnn.io/data/gis/cnn-disputed-lines-50m.geojson",
    "world_land": "https://ix.cnn.io/data/gis/world_land_50m.geojson",
    "us_states": "https://ix.cnn.io/data/gis/us_states.geojson",
    "us_counties": "https://ix.cnn.io/data/gis/us_counties.zip",
}
