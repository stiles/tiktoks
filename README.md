# TikTok stories

This repo holds code-driven posts for TikTok: one-off data stories, geography quizzes and mystery maps.

Every output is a static `1080x1920` PNG slide for a carousel post. The code is Python because the early work is data, maps and batch exports.

## Setup

```bash
uv sync --extra dev
uv run python scripts/build_crosswalk.py
```

The crosswalk step is required once. The boundary file carries no ISO codes, so without it nothing joins to Wikidata or the World Bank.

## Commands

```bash
make quiz TIER=medium    # build and render the next quiz batch
make rebuild             # re-render every post from content/
make quiz-status         # pool depth per tier, and validate every name
make catalog         # render every guess-the-map post from the query catalog
make catalog-list    # show what is in the catalog
make crosswalk       # rebuild the country code crosswalk
make styles          # render the test slides in all three themes
make example         # run the example story end to end
make check           # lint and test
```

The CLI directly:

```bash
uv run tiktoks quiz next --tier medium --count 3
uv run tiktoks quiz next --tier expert --count 3 --dry-run
uv run tiktoks quiz status --validate
uv run tiktoks geo-quiz --config posts/geo-quiz/geo-medium-001/quiz.yaml
uv run tiktoks catalog --slug nato-members
uv run tiktoks catalog --all
uv run tiktoks guess-map --config content/guess-map-csv-example/guess_map.yaml
uv run tiktoks story --slug 2026-new-story
```

Render commands take `--theme night|paper|poster` and write to `<post dir>/<theme>/`. The default is `night`.

## Repo layout

Two rules cover most of it. You write in `content/`. The code writes to `posts/`,
`data/` and `review/`, and everything it writes can be rebuilt.

```
content/                     everything written by hand
  countries.csv                the geo-quiz country pool
  guess-map.yaml               the guess-the-map query catalog
  guess-map-csv-example/       a map built from a local CSV instead of a query
  stories/<slug>/              story config and its fetch, process and render scripts

posts/                       one directory per post, rebuildable from content/
  geo-quiz/<slug>/
    quiz.yaml                  tracked: what this post contained
    night/
      post.json                tracked: the key that ties this to a TikTok post ID
      *.png                    ignored
  guess-map/<slug>/
  stories/<slug>/

data/                        fetched and derived, ignored
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

A prompt and its answer share one map rect so the swipe reads as a reveal. See `shared_slot`.

Cover slides break the top-down flow. `backdrop_axes()` puts a full-bleed map behind everything, `scrim()` washes it toward the background so type reads over it, and `centered_stack()` measures a stack of text and centers it in the space that TikTok does not cover.

## Posts and the manifest

A render produces a `post.json` beside the PNGs, holding the slug, format, difficulty, slide order, alt text, sources, caption, render time, git SHA and config hash. That is what ties a rendered batch to a TikTok post later, so metrics can be attributed to a format instead of guessed at.

The only field that cannot be known at render time is the post ID. Fill in the `publish` block after posting.

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
6. When it goes out, fill in the `publish` block in that post's `post.json`. That is the only thing the renderer cannot know, and it is what the metrics work in `docs/metrics.md` joins on.

## The country pool

Quiz batches are drawn from `content/countries.csv` rather than written by hand, so batch 020 does not repeat batch 003.

```bash
uv run tiktoks quiz status                       # depth per tier
uv run tiktoks quiz next --tier hard --count 3   # build, render, record
```

The pool holds 100 countries, 25 per tier. Selection is least-recently-used, recency ahead of use count: never-used countries first, then whatever ran longest ago. Rendering writes `times_used` and `last_rendered` back, and the batch config lands in `posts/geo-quiz/geo-<tier>-NNN/quiz.yaml` as the record of what the post contained.

Columns: `name` is what the answer slide says, `match_name` is the polygon to look up when the two differ (the boundary file still calls Eswatini "Swaziland"), and `center_lon`, `center_lat`, `zoom` and `context` override the default framing.

Run `uv run tiktoks quiz status --validate` after editing the pool. It resolves every name against the boundary file, which beats a batch failing halfway through a render.

## Config options

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
