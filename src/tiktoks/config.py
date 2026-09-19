from tiktoks.paths import repo_root

CANVAS_SIZE = (1080, 1920)

ROOT = repo_root()

# Everything written by hand lives under content/. Everything the renderer makes
# lives under posts/, data/ or review/, and is regenerable.
CONTENT_DIR = ROOT / "content"
POSTS_DIR = ROOT / "posts"
DATA_DIR = ROOT / "data"
REFERENCE_DIR = DATA_DIR / "reference"
REVIEW_DIR = ROOT / "review"

COUNTRY_POOL_PATH = CONTENT_DIR / "countries.csv"
GUESS_MAP_CATALOG_PATH = CONTENT_DIR / "guess-map.yaml"
STORIES_DIR = CONTENT_DIR / "stories"
CROSSWALK_PATH = REFERENCE_DIR / "country_crosswalk.csv"
YOUTUBE_CLIENT_SECRETS = DATA_DIR / "youtube-client-secrets.json"
YOUTUBE_TOKEN = DATA_DIR / "youtube-token.json"
PUBLISH_LOG_PATH = DATA_DIR / "publish.csv"
AUDIO_DIR = CONTENT_DIR / "audio"
AUDIO_CATALOG_PATH = AUDIO_DIR / "catalog.yaml"
AUDIO_BED_PATH = AUDIO_DIR / "bed.mp3"

GIS_URLS = {
    "countries": "https://stilesdata.com/gis/cnn-country-polys-50m.geojson",
    "country_lines": "https://stilesdata.com/gis/cnn-country-lines-50m.geojson",
    "disputed_lines": "https://stilesdata.com/gis/cnn-disputed-lines-50m.geojson",
    "world_land": "https://stilesdata.com/gis/world_land_50m.geojson",
    "us_states": "https://stilesdata.com/gis/us_states.geojson",
    "us_counties": "https://stilesdata.com/gis/us_counties.zip",
}
