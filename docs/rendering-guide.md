# Rendering and geography config reference

[Usage and format selection](../README.md) · [Example gallery](../EXAMPLES.md)

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

## Country overrides

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
