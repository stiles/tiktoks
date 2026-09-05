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
uv run tiktoks geo-quiz --config quizzes/geo/geo-medium-001/quiz.yaml
uv run tiktoks catalog --slug nato-members
uv run tiktoks catalog --all
uv run tiktoks guess-map --config quizzes/guess-map/nato-members-csv/guess_map.yaml
uv run tiktoks story --slug 2026-new-story
```

Render commands take `--theme night|paper|poster` and write to `<config dir>/output/<theme>/`. The default is `night`.

## Repo layout

- `src/tiktoks/` has the slide layout, mapping, style and CLI helpers.
- `src/tiktoks/sources/` has the Wikidata and World Bank fetchers.
- `content/guess-map/catalog.yaml` is the query catalog: one entry per guess-the-map post.
- `content/geo-quiz/countries.csv` is the country pool that quiz batches are drawn from.
- `templates/` has starter files for new one-off stories, geography quizzes and guess-map posts.
- `stories/` has dated one-off stories.
- `quizzes/geo/` has country quiz batches. `quizzes/guess-map/` has mystery map output.
- `scripts/` has review tools. `style_lab.py` renders test slides in every theme,
  `world_projections.py` compares world projections, `safe_overlay.py` draws the
  assumed TikTok interface zones over a slide, `build_crosswalk.py` rebuilds the
  country code table.
- `tests/` covers text fitting, map framing, the crosswalk and the layout rules.
- `docs/` has idea lists, rollout notes, the visual style guide and the roadmap.
- `PLANNING.md` is the roadmap and menu of work.
- `data/reference/` caches boundary files, API responses and the crosswalk. Generated data stays out of git.

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
6. Add a row to `data/publish-log.csv` when it goes out, and fill in the `publish` block in `post.json`.

## The country pool

Quiz batches are drawn from `content/geo-quiz/countries.csv` rather than written by hand, so batch 020 does not repeat batch 003.

```bash
uv run tiktoks quiz status                       # depth per tier
uv run tiktoks quiz next --tier hard --count 3   # build, render, record
```

Selection is least-recently-used, recency ahead of use count: never-used countries first, then whatever ran longest ago. Rendering writes `times_used` and `last_rendered` back, and the batch config lands in `quizzes/geo/geo-<tier>-NNN/quiz.yaml` as the record of what the post contained.

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
