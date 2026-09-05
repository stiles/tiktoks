from tiktoks.paths import repo_root

CANVAS_SIZE = (1080, 1920)

ROOT = repo_root()
DATA_DIR = ROOT / "data"
REFERENCE_DIR = DATA_DIR / "reference"
CONTENT_DIR = ROOT / "content"
OUTPUT_DIR = ROOT / "output"

CROSSWALK_PATH = REFERENCE_DIR / "country_crosswalk.csv"

GIS_URLS = {
    "countries": "https://stilesdata.com/gis/cnn-country-polys-50m.geojson",
    "country_lines": "https://stilesdata.com/gis/cnn-country-lines-50m.geojson",
    "disputed_lines": "https://stilesdata.com/gis/cnn-disputed-lines-50m.geojson",
    "world_land": "https://stilesdata.com/gis/world_land_50m.geojson",
    "us_states": "https://stilesdata.com/gis/us_states.geojson",
    "us_counties": "https://stilesdata.com/gis/us_counties.zip",
}
