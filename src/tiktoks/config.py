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
    "countries": "https://stilesdata.com/gis/cnn-country-polys-50m.geojson",
    "country_lines": "https://stilesdata.com/gis/cnn-country-lines-50m.geojson",
    "disputed_lines": "https://stilesdata.com/gis/cnn-disputed-lines-50m.geojson",
    "world_land": "https://stilesdata.com/gis/world_land_50m.geojson",
    "us_states": "https://stilesdata.com/gis/us_states.geojson",
    "us_counties": "https://stilesdata.com/gis/us_counties.zip",
}
