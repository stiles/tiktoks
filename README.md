# TikTok stories

This repo holds code-driven posts for TikTok and YouTube Shorts: one-off data
stories, geography quizzes, country area comparisons and mystery maps.

Every post starts as a static `1080x1920` PNG slide. TikTok gets a carousel.
YouTube Shorts gets an MP4 assembled from the same sequence. The code is Python
because the early work is data, maps and batch exports.

## Setup

```bash
uv sync --extra dev
uv run python scripts/build_crosswalk.py
```

The crosswalk step is required once. The boundary file carries no ISO codes, so without it nothing joins to Wikidata or the World Bank.

## Commands

```bash
make quiz TIER=medium    # build and render the next quiz batch
make quiz TIER=master COUNT=6  # isolated outlines, regional answer reveals
make quiz-silhouette TIER=hard  # borderless shape quiz; difficulty controls context zoom
make quiz-progressive TIER=medium  # tight prompt, wider hint, then answer
make area-quiz                 # land-area pilot, night theme
make neighbors-quiz THEME=paper  # borders and landlocked-country pilot
make area-quiz SLUG=area-001 THEME=paper  # choose a curated batch and theme
make rebuild             # re-render every post from content/
make quiz-status         # pool depth per tier, and validate every name
make catalog         # render every guess-the-map post from the query catalog
make catalog-list    # show what is in the catalog
make publish-status  # what has gone out on TikTok, and what has not
make crosswalk       # rebuild the country code crosswalk
make styles          # render the test slides in all three themes
make example         # run the example story end to end
make check           # lint and test
```

The CLI directly:

```bash
uv run tiktoks quiz next --tier medium --count 3
uv run tiktoks quiz next --tier easy --count 3 --variant silhouette
uv run tiktoks quiz next --tier medium --count 3 --variant progressive
uv run tiktoks quiz next --tier expert --count 3 --dry-run
uv run tiktoks quiz status --validate
uv run tiktoks geo-quiz --config posts/geo-quiz/geo-medium-001/quiz.yaml
uv run tiktoks area-quiz --config content/area-quiz/area-001/quiz.yaml --theme night
uv run tiktoks area-quiz --config content/area-quiz/area-001/quiz.yaml --theme paper
uv run tiktoks neighbors-quiz --config content/neighbors-quiz/neighbors-001/quiz.yaml --theme paper
uv run tiktoks catalog --slug nato-members
uv run tiktoks catalog --all
uv run tiktoks guess-map --config content/guess-map-csv-example/guess_map.yaml
uv run tiktoks story --slug 2026-new-story
uv run tiktoks video --dir posts/guess-map/opec-members/night
uv run tiktoks stage --dir posts/geo-quiz/geo-medium-001/night --open
uv run tiktoks youtube auth
uv run tiktoks youtube upload --dir posts/guess-map/opec-members/night
uv run tiktoks publish mark geo-medium-001
uv run tiktoks publish status
```

Render commands take `--theme night|paper|poster` and write to `<post dir>/<theme>/`. The default is `night`.

## Repo layout

Two rules cover most of it. You write in `content/`. The code writes to `posts/`,
`data/` and `review/`, and everything it writes can be rebuilt.

```
content/                     everything written by hand
  countries.csv                the geo-quiz country pool
  area-quiz/<slug>/            curated A/B questions, saved source data and methodology
  guess-map.yaml               the guess-the-map query catalog
  guess-map-csv-example/       a map built from a local CSV instead of a query
  stories/<slug>/              story config and its fetch, process and render scripts
  audio/                       default Shorts bed and its license sidecar

posts/                       one directory per post, rebuildable from content/
  area-quiz/<slug>/<theme>/     comparison quiz slides, contact sheet and post.json
  geo-quiz/<slug>/
    quiz.yaml                  tracked: what this post contained
    night/
      post.json                tracked: platform post IDs live here
      *.png                    ignored
      *.mp4                    ignored
  guess-map/<slug>/
  stories/<slug>/

data/                        fetched and derived, mostly ignored
  publish.csv                  TikTok posts, written by `tiktoks publish mark`
  reference/                   boundary files, API caches, the country crosswalk
  stories/<slug>/              a story's raw and processed data

review/                      throwaway renders from the review scripts, ignored

src/tiktoks/                 the library
  sources/                     Wikidata and World Bank fetchers
scripts/                     one-off and review tools
templates/story/             starter files for `tiktoks story`
tests/
docs/                        style guide, idea lists, metrics design
PLANNING.md                  the ordered list of what to build next
```

Nothing under `posts/` is precious. `make rebuild` regenerates every batch and
catalog entry from `content/`.

## How a slide is built

`Slide` stacks a kicker, title and dek from the top and a footer from the bottom, then hands the map whatever vertical space is left. Titles wrap against measured glyph widths and shrink to fit a line budget, so a long headline never runs off the canvas.

Layout respects TikTok's own interface, not just the theme margins. The app covers roughly the bottom 400px with the caption and username, the top 130px with its tab bar, and a column down the right with the button rail. Those zones live in `src/tiktoks/safe.py`, and `Slide.check_layout()` reports any text or chip that lands in one. `Post` runs that check on every slide and refuses to finish a batch that fails it.

The numbers in `safe.py` were measured from a screenshot, not read from a spec. Check them against your own phone with:

```bash
uv run python scripts/safe_overlay.py path/to/slide.png
```

Maps are projected before they are drawn. Country zooms use Lambert azimuthal equal area centered on the country; world maps use Equal Earth. `prepare_country` and `prepare_world` return a projected frame and the window to show it in, which lets the caller size the map box to the data instead of cropping it into a portrait slot.

Quiz prompts, hints and answers use Natural Earth's 1:10-million Admin 0 country
boundaries, cached locally on first use. Quiz covers and other world-map products
keep the existing 1:50-million CNN polygons. The 10m loader accepts the legacy
quiz names for Eswatini and São Tomé and Príncipe; `quiz status --validate` checks
the detailed data. A quiz's `countries_geojson` override still supplies both its
country maps and cover. Each quiz manifest records the geometry sources.

A prompt and its answer share one map rect so the swipe reads as a reveal. See `shared_slot`.

Cover slides break the top-down flow. `backdrop_axes()` puts a full-bleed map behind everything, `scrim()` washes it toward the background so type reads over it, and `centered_stack()` measures a stack of text and centers it in the space that TikTok does not cover.

## Posts and the manifest

A render produces a `post.json` beside the PNGs, holding the slug, format, difficulty, slide order, alt text, sources, caption, render time, git SHA and config hash. That is what ties a rendered batch to a TikTok post later, so metrics can be attributed to a format instead of guessed at.

The only fields that cannot be known at render time are the platform post IDs. After a TikTok upload, record it with `tiktoks publish mark <slug>`. That writes `publish.posted_at` on the post's `post.json` and updates `data/publish.csv`. `tiktoks youtube upload` writes the YouTube id itself.

```bash
uv run tiktoks publish mark geo-expert-007
uv run tiktoks publish mark geo-expert-007 --url URL --notes 'asked for more islands'
uv run tiktoks publish status
uv run tiktoks publish status --unpublished
```

## Phone handoff

TikTok on iOS only sees the camera roll, not `posts/` on your Mac. AirDrop works but
the files often land in Downloads, and carousel order is easy to scramble.

`tiktoks stage` copies a rendered post into an inbox folder with zero-padded names
in `post.json` order (`01-cover.png`, `02-prompt.png`, …) plus `caption.txt`.

```bash
uv run tiktoks stage --dir posts/geo-quiz/geo-medium-001/night --open
uv run tiktoks stage --dir posts/stories/2026-ssa-name-karen --photos
```

Default destination is `iCloud Drive/TikTok Inbox/<slug>/` when iCloud Drive is
enabled on the Mac. Without iCloud, slides go to `review/phone-inbox/<slug>/`.

**iCloud Drive path:** On the phone, open Files → TikTok Inbox → the slug folder.
Select the numbered PNGs in order → Share → Save to Photos. Then create the TikTok
carousel from Recents.

**Photos path:** `--photos` imports on the Mac into the Photos library. With iCloud
Photos on, they show up on the phone without AirDrop. Pick them in TikTok in the
same numbered order.

Stories and quizzes need a `post.json` beside the PNGs so staging knows swipe order.

## YouTube Shorts

Image carousels on the Shorts feed are channel posts, capped at 10 images and
suggested as 1:1. They have no API. These slides are 9:16 and a three-country
quiz is already eight frames, so Shorts here means a video.

`tiktoks video` holds each slide by kind (longer on the prompt, a cut on the
answer) and writes `{slug}.mp4` next to the PNGs. ffmpeg has to be on PATH.

The beds live in `content/audio/catalog.yaml`. Default is Kevin MacLeod's
"Comfortable Mystery 2" (CC BY 3.0). The other two are Artlist tracks: they need
an active Artlist license and the YouTube channel on [Clearlist](https://help.artlist.io/hc/en-us/articles/29490991524253-Understanding-Artlist-s-license),
or the upload can take a Content ID claim.

```bash
uv run tiktoks video --list-audio
uv run tiktoks video --dir posts/geo-quiz/geo-easy-001/night
uv run tiktoks video --dir posts/geo-quiz/geo-easy-001/night --audio groovy-panda
uv run tiktoks video --dir posts/geo-quiz/geo-easy-001/night --silent
```

Upload uses the ordinary YouTube Data API `videos.insert` endpoint. A vertical
MP4 under three minutes is classified as a Short. There is no Shorts flag.

1. Enable YouTube Data API v3 on a Google Cloud project.
2. Create an OAuth client of type Desktop and save the JSON as
   `data/youtube-client-secrets.json`.
3. Add yourself as a test user on the OAuth consent screen.
4. Install the extra and authorize once:

```bash
uv sync --extra youtube
uv run tiktoks youtube auth
uv run tiktoks youtube upload --dir posts/geo-quiz/geo-easy-001/night
```

Uploads default to private so you can check the draft in Studio. Pass
`--privacy unlisted` or `--privacy public` when it looks right. The video id
lands in `publish.youtube` on that post's `post.json`. Re-rendering the slides
keeps it.

## The query catalog

Most guess-the-map ideas are one query each, so a post is a catalog entry rather than a hand-built CSV. Data is fetched, joined on ISO 3166-1 alpha-3 through `data/reference/country_crosswalk.csv`, and cached on disk.

```yaml
- slug: nato-members
  difficulty: easy
  map_type: binary
  prompt: What do these countries have in common?
  answer: They are NATO members
  source: "Source: Wikidata membership property. Boundaries: Natural Earth."
  challenge: Name the two newest NATO members.
  expect:
    count: 32
  fetch:
    kind: wikidata_members
    property: P463
    value: Q7184
    include: [DNK, NLD]
```

`fetch.kind` is one of `wikidata_members`, `wikidata_values`, `wikidata_query`, `worldbank` or `csv`.

Wikidata is not a membership registry, and a map with the wrong countries shaded is worse than no map. Two guards:

- `expect.count` or `expect.min_countries` fails the render when a query returns an unexpected number of countries. That catches a wrong QID, a changed property or a silent upstream edit.
- `include` and `exclude` correct known errors in the open. NATO comes back as 30 because Denmark and the Netherlands record the statement on the kingdom rather than the country; Angola still reads as OPEC after leaving in 2024.

## Workflow

1. Add or pick an idea from `docs/`, or add a catalog entry.
2. Copy a template or run `uv run tiktoks story --slug YYYY-topic`.
3. Fetch and process the data with scripts or a notebook.
4. Render the slides. The contact sheet is written automatically.
5. Check the batch at thumbnail size before opening any single slide.
6. When it goes out, run `tiktoks publish mark <slug>`. That is the only thing the renderer cannot know, and it is what the metrics work in `docs/metrics.md` joins on.

## Country comparison quizzes

### Know your neighbors

The borders pilot uses six sourced A/B questions and labeled regional map reveals:

```bash
uv run tiktoks neighbors-quiz --config content/neighbors-quiz/neighbors-001/quiz.yaml --theme paper
uv run tiktoks neighbors-quiz --config content/neighbors-quiz/neighbors-001/quiz.yaml --theme night
make neighbors-quiz SLUG=neighbors-001 THEME=night
```

Outputs go to `posts/neighbors-quiz/neighbors-001/<theme>/`. The default is `night`;
`paper` and `poster` are accepted too. See the [pilot guide](content/neighbors-quiz/neighbors-001/README.md)
for verification sources, config fields and staging commands. It is curated
separately from the country pool and is not included in `make rebuild`.

### Land area

For future topics, see [Factbook quiz ideas](docs/factbook-quiz-ideas.md): an audit
of the archived source and candidates about borders, elevation and landlocked countries.

`area-quiz` is the CLI content type for curated, two-choice land-area quizzes.
It supports `night`, `paper`, and `poster`; omitting `--theme` uses `night`.
For the pilot, run:

```bash
uv run tiktoks area-quiz --config content/area-quiz/area-001/quiz.yaml --theme night
uv run tiktoks area-quiz --config content/area-quiz/area-001/quiz.yaml --theme paper
uv run tiktoks area-quiz --help
```

Or use `make area-quiz SLUG=area-001 THEME=night`. The Make shortcut defaults to
`area-001` and `night` when those variables are omitted.

Each render writes 14 slides, a contact sheet and a manifest to
`posts/area-quiz/area-001/<theme>/`. Night and paper outputs coexist, so rendering
one theme does not replace the other. To prepare the night version for posting:

```bash
uv run tiktoks stage --dir posts/area-quiz/area-001/night --open
uv run tiktoks video --dir posts/area-quiz/area-001/night
```

The saved 2023 World Bank/FAO figures determine the answers; reveals show country
outlines at the same map scale. Source data and methodology live beside the config.
Questions and answers label choices with colons: `A: Italy`, `B: Japan`.
Paper-theme answer slides place the outlines directly on the cream background,
without a blue water panel or border. Prompts show only the choices; answer maps
and values appear after the swipe.

See [the pilot guide](content/area-quiz/area-001/README.md) for data definitions,
the config fields and instructions for making another batch. Comparison quizzes
are curated separately from the country pool and do not change its usage counters.
Render them with `area-quiz`; `make rebuild` does not include this format yet.

## The country pool

Quiz batches are drawn from `content/countries.csv` rather than written by hand, so batch 020 does not repeat batch 003.

```bash
uv run tiktoks quiz status                       # depth per tier
uv run tiktoks quiz next --tier hard --count 3   # build, render, record
```

`quiz next` builds one post. `--count` is how many countries go in that post, not how many quizzes to make. `--variant silhouette` switches to a shape-first format: no country borders, more surrounding land, and difficulty changes how much context the frame gives away. `--variant progressive` adds a middle hint slide with a wider frame, so each country goes prompt, hint, answer. On easier progressive tiers, the hint and answer add country borders back in with a more visible stroke while the first prompt stays borderless. To render several, loop it:

```bash
for tier in easy medium hard expert; do
  for i in $(seq 5); do
    uv run tiktoks quiz next --tier "$tier" --count 3 --theme paper
  done
done
```

That example is five quizzes in each tier, three countries each, in the paper theme. Each pass writes usage back to the pool so the next pick does not repeat the last one. `--dry-run` does not write usage, so looping a dry run shows the same countries every time.

The pool holds 108 countries, 27 per tier. Selection is least-recently-used, recency ahead of use count: never-used countries first, then whatever ran longest ago. Rendering writes `times_used` and `last_rendered` back, and the batch config lands in `posts/geo-quiz/geo-<tier>-NNN/quiz.yaml` as the record of what the post contained. Silhouette and progressive batches write to `posts/geo-quiz/geo-<variant>-<tier>-NNN/quiz.yaml` and draw from the whole pool, because there the tier is the amount of context rather than the country bucket.

Columns: `name` is what the answer slide says, `match_name` is the polygon to look up when the two differ (the boundary file still calls Eswatini "Swaziland"), and `center_lon`, `center_lat`, `zoom` and `context` override the default framing.

Usage recency is recorded with a UTC timestamp so consecutive batches on the same
day rotate through the pool before repeating low-use countries. Existing date-only
records remain supported; lifetime use count breaks ties only after recency.

Run `uv run tiktoks quiz status --validate` after editing the pool. It resolves every name against the boundary file, which beats a batch failing halfway through a render.

## Config options

### Master quizzes

`uv run tiktoks quiz next --tier master --count 6` builds an outline-only quiz.
Master draws from the expert pool and shares its usage counters, so recent expert
questions move to the back of the queue. It keeps the complete country outline,
north up, with no surrounding land or locator rings. Each answer restores a
regional map. Do not combine Master with `--variant`; its format is built in.
`quiz status` shows Master as the same candidate pool as Expert, not extra countries.

The first curated batch is `posts/geo-quiz/geo-master-001/quiz.yaml`.

### Country overrides

A batch config takes a `name` and `fact` per country, plus optional overrides. Match on the polygon `name` column, which uses short forms: `United States`, not `United States of America`.

```yaml
countries:
  - name: United States
    fact: It has the world's third largest population.
    match_name: United States   # polygon lookup, when it differs from the display name
    hook: Everyone thinks this one is easy.   # overrides the per-difficulty hook
    center: [-98.5, 39.5]   # projection center, lon/lat
    zoom: 1.4               # >1 pulls back, <1 moves in
    context: world          # highlight on a world map instead of a regional zoom
```

A batch opens on a cover slide: a world map behind the question, the difficulty, the country count and a request for a score in the comments. Starting on the first map asks the viewer to work out what the post even is. Override the headline with `cover_title` in the batch config.

Prompt slides then lead with a hook rather than an instruction, carry a question counter, and the batch ends on a scorecard. Hooks rotate through a per-tier pool so ten prompts do not read identically.

A country that covers too little of its map window gets a locator ring drawn around it. That is what makes the expert island tier postable: Comoros needs a window wide enough to show Madagascar, at which point the country itself is specks.
