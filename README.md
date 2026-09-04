# TikTok stories

This repo holds code-driven posts for TikTok: one-off data stories, geography quizzes and mystery maps.

Every output is a static `1080x1920` PNG slide for a carousel post. The code is Python because the early work is data, maps and batch exports.

## Setup

```bash
uv sync --extra dev
```

## Commands

```bash
make quiz
make guess-map
make styles
make example
```

You can also call the CLI directly:

```bash
uv run tiktoks geo-quiz --config quizzes/geo/world-countries-001/quiz.yaml
uv run tiktoks guess-map --config quizzes/guess-map/nato-members/guess_map.yaml
uv run tiktoks story --slug 2026-new-story
```

Both render commands take `--theme night|paper|poster` and write to `<config dir>/output/<theme>/`. The default is `night`.

## Repo layout

- `src/tiktoks/` has the slide layout, mapping, style and CLI helpers.
- `templates/` has starter files for new one-off stories, geography quizzes and guess-map posts.
- `stories/` has dated one-off stories.
- `quizzes/geo/` has country quiz batches.
- `quizzes/guess-map/` has mystery map batches.
- `scripts/` has review tools: `style_lab.py` renders the same test slides in every theme, `world_projections.py` compares world projections.
- `docs/` has idea lists, rollout notes, the visual style guide and the roadmap.
- `data/reference/` caches boundary files downloaded from S3. Generated data stays out of git.

## How a slide is built

`Slide` stacks a kicker, title and dek from the top and a footer from the bottom, then hands the map whatever vertical space is left. Titles wrap against measured glyph widths and shrink to fit a line budget, so a long headline never runs off the canvas.

Maps are projected before they are drawn. Country zooms use Lambert azimuthal equal area centered on the country; world maps use Equal Earth. `prepare_country` and `prepare_world` return a projected frame and the window to show it in, which lets the caller size the map box to the data instead of cropping it into a portrait slot.

A prompt and its answer share one map rect so the swipe reads as a reveal. See `shared_slot`.

## Workflow

1. Add or pick an idea from `docs/`.
2. Copy a template or run `uv run tiktoks story --slug YYYY-topic`.
3. Fetch and process the data with scripts or a notebook.
4. Render the slides.
5. Tile the batch with `contact_sheet()` and check it at thumbnail size before opening any single slide.

6. Add a row to `data/publish-log.csv` when it goes out.

Every post should carry enough metadata to rebuild it later: source URL, run date, join keys, difficulty and export path. The publish log is what ties a rendered batch to its TikTok post ID, and without it the metrics in `docs/roadmap.md` cannot be attributed to a format.

## Config options

Geo quiz entries take a `name` and `fact`, plus optional overrides when the default framing is wrong:

```yaml
countries:
  - name: United States of America
    fact: It has the world's third largest population.
    center: [-98.5, 39.5]   # projection center, lon/lat
    zoom: 1.4               # >1 pulls back, <1 moves in
    context: world          # highlight on a world map instead of a regional zoom
```
