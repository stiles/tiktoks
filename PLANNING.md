# Planning

A menu of work, roughly ordered by impact. Each item says what it changes and why
it matters. Nothing here is a commitment; pick from it.

Status keys: `done`, `next`, `open`.

---

## 1. Enforce the TikTok safe area — `done`

`SAFE_AREA` was defined in `config.py`, exported from `__init__.py` and read by
nothing. Its bottom value was 180px. TikTok's caption, username and music ticker
cover far more than that, and the right-hand button rail covers a column that runs
most of the height of the frame.

Every slide rendered before this fix put its source line, call-to-action pill and
legend underneath the app's own UI.

The fix is a real zone model in `safe.py`, enforced in `Slide.__init__`, plus a
debug overlay so the zones can be checked against a screenshot.

## 2. Check layout mechanically, not by eye — `done`

`docs/visual-style.md` asks a human to confirm that text stays inside the margins
and that a prompt and its answer put the map in the same place. Both are testable.

`Slide` now records every text artist it draws. `check_layout()` returns the ones
that fall outside the content box or land in a reserved zone. A pixel scan would
false-positive on world maps, which bleed to the canvas edge on purpose, so the
check runs on text bounding boxes instead.

## 3. Make `Post` a first-class object — `done`

`geo_quiz.py` and `guess_map.py` were the same function twice: read YAML, resolve
the theme, work out the output directory, build a prompt and answer, `shared_slot`,
loop, save. The post itself existed only as a filename convention.

`Post` owns an ordered slide list and its metadata, and writes `post.json` next to
the PNGs: slug, format, difficulty, slide order, alt text, sources, caption,
render time, git SHA, config hash.

That is the join key `docs/metrics.md` calls "the join problem." The roadmap
proposed solving it with a CSV filled in by hand at publish time. It should be free
at render time. The only field a human adds later is the TikTok post ID.

## 4. Wikidata and World Bank as the map engine — `done`

Most of `docs/guess-the-map-ideas.md` is one query each. Countries that drive on
the left, euro users, Olympic hosts, single-land-border countries: all Wikidata.
GDP per capita, median age, electricity mix: World Bank.

The blocker was the join. The CNN country polys carry `sovereignt`, `name` and
`name_long` and no ISO code, so there is nothing to join a Wikidata result to.
`scripts/build_crosswalk.py` builds `data/reference/country_crosswalk.csv` once,
mapping each polygon name to an ISO A3 code and a Wikidata QID, with manual
overrides for the cases that do not match on label.

After that a guess-the-map post is a catalog entry, not a hand-built CSV.

## 5. Rewrite the hook — `done`

The first frame was a label. "NAME THAT COUNTRY / Which country is highlighted?"
is an instruction, and an instruction does not stop a thumb. The frame that does
makes a claim: most people miss this one, nine in ten get this wrong.

Prompt slides now take a `hook` from the config and fall back to a per-difficulty
default. The map gets more of the canvas because the dek is gone from prompts.

## 6. Score the quiz — `done`

The difficulty badge was decoration. It is now a running counter, and each batch
ends on a scorecard.

Finish rate is the metric `docs/metrics.md` correctly identifies as the one worth
reading, and a reason to reach the last slide is the cheapest way to move it.

## 6b. Cover slide — `done`

A quiz opened on its first map, which asks the viewer to work out what the post
even is before deciding whether to stay. It opens on a cover now: a world map
behind the question, the difficulty, the country count and a request for a score.

This needed three new primitives, because the normal layout is left-aligned and
top-down. `backdrop_axes()` is a full-bleed axes behind everything, `scrim()`
washes it toward the background so type reads over it, and `centered_stack()`
measures a stack of text and centers it in the band TikTok leaves visible.

A 2:1 world map fitted to a 9:16 frame is a thin strip across the middle, so the
backdrop takes a `zoom` that trades the far east and west for height. It is
wallpaper; the crop does not matter.

All 17 existing batches were re-rendered with a cover.

## 7. Content catalog instead of hand-written batches — `done`

`docs/geo-quiz-rollout.md` holds 40 countries across four tiers as a markdown list,
and `quizzes/geo/world-countries-001/quiz.yaml` repeated ten of them. That works for
batch 001 and breaks by batch 020, when the question becomes which countries have
already run.

The pool lives in `content/countries.csv`. A batch is a query against it:

```
tiktoks quiz status --validate
tiktoks quiz next --tier medium --count 3
```

Selection is least-recently-used, recency ahead of use count. Rendering writes the
usage back, so the next batch does not repeat the last one. The batch YAML still
lands on disk as the record of what a post contained.

Two things this surfaced. The pool needs `match_name` separate from `name`, because
the boundary file still calls Eswatini "Swaziland" and the answer slide should not.
And the expert tier was rendering unpostable slides, which is item 12 below.

## 7b. Repo layout — `done`

Content, configs and output had grown into three different couplings across three
formats, plus a `quizzes/` tree that held guess-maps. Worse, `**/output/` in
`.gitignore` was swallowing every `post.json`, so the manifest built as the metrics
join key was not actually in the repo.

Now: `content/` is everything written by hand, `posts/` is one directory per post,
`data/` is fetched and derived, `review/` is throwaway. Under `posts/`, `quiz.yaml`
and `post.json` are tracked and the PNGs are not. `make rebuild` regenerates the
lot from `content/`.

Also folded in: the dead `templates/geo_quiz` and `templates/guess_map`, which
nothing had referenced since the pool and catalog landed, and `docs/roadmap.md`,
which duplicated this file. Its metrics design moved to `docs/metrics.md`.

## 8. Metrics collector — `open`

Scoped in detail in `docs/metrics.md`. TikTok analytics do not backfill, so this
comes before a posting schedule, not after it.

Item 3 removes the hard part. `post.json` already carries the format, difficulty
and slug, so `metrics report` is a join against the snapshots rather than a
data-entry problem.

Build order: `metrics auth` to store the TikAPI key, `metrics pull` for one dated
snapshot, a daily GitHub Action shaped like the bots repo, then `metrics report`
to rank formats by finish rate.

## 9. Video assembly — `open`

The rig already produces the frames. An ffmpeg pass that turns a slide sequence
into an MP4 (a slow push on the map, a cut on the reveal) is a small amount of code
and doubles the surface the post can occupy.

Worth doing after item 8, so there is a way to tell whether it helped.

## 10. Delay the reveal — `open`

Prompt to answer is one swipe. Prompt, then a zoomed-out regional view, then the
answer is two, with an escalation between them. `prepare_country` already takes a
`zoom`, so the middle frame is mostly a config change.

## 11. US geography — `open`

`GIS_URLS` has `us_states` and `us_counties` and nothing loads them. Much of the
guess-the-map backlog is county level.

Needs an Albers projection for the lower 48, an inset scheme for Alaska and Hawaii,
and a FIPS join.

## 12. Island insets — `partly done`

Comoros and Sao Tome need a window wide enough to show a reference coastline, at
which point the country is specks. Rather than an inset, `draw_highlight` now rings
a highlight that covers too little of its window. One map, one projection, one
shared rect across the prompt and the answer.

The threshold is an area share, not a bounding box: a scattered archipelago has a
wide box and almost no ink in it. Measured across the pool, the two island nations
that need a ring sit at 0.0002 and the smallest country that does not (the Gambia)
at 0.0085.

A true inset is still the better answer for the Maldives and Fiji, which are not in
the pool yet.

## 13. Choropleth binning beyond quantiles — `open`

`draw_choropleth` hardcodes the quantiles scheme. Some measures want natural breaks
or fixed thresholds, and a diverging scale needs a real midpoint.

## 14. Editorial note on picking maps — `open`

Guess-the-map works when the map invites a wrong first guess. A map that looks like
population and turns out to be something else starts arguments; a clean map of an
obvious thing gets nods. Worth making misdirection a selection criterion in
`docs/guess-the-map-ideas.md` rather than picking the most legible datasets.

## Smaller cleanups

- `config.py` and `paths.py` both define the repo root. `done`
- `Slide.map_aspect` was set as a side effect of `map_axes()` and read by every
  caller afterward. Now returned. `done`
- No tests existed. `fit`, `country_match`, `core_parts` and `pad_bounds` are pure
  and now covered, alongside the pool, batch building and the locator rule. `done`
- The hook was one string per tier, so ten prompt slides read identically on the
  contact sheet. It rotates through a pool now. `done`

---

## Original brief

I want this repo to be the home for code-driven stories I tell on TikTok.

### A few storytelling forms

- One-off stories based on the news, eg, a chart showing a time series of a poll
  showing presidential approval rates, or the evolution of a given name's
  popularity in Social Security records. These are topically and news driven ideas.

- Geo-based quizzes: These would be picture posts with world geography quizzes, eg,
  a slide show with a no-label map and a country highlighted. The user horizontally
  scrolls through static images: Country, answer, country, answer, country, answer.
  Some are easy, medium, hard, expert. Ideally these are scripted and output in
  bulk so they can be published on a regular schedule, once we set on a strong
  visual style and tone.

- Guess the map! Each post is a single choropleth or other thematic map and the
  user must guess what it is, eg, a shaded map of African American population in
  the US, or a map with NATO countries shaded, or a world map shaded by GDP. The
  user has to guess and get the answer either on the next slide or the comments.
  Again: Easy, medium, hard.

### Libraries we can leverage

- ezesri: A Python package for extracting data and metadata from Esri REST API
  endpoints. It provides an API, CLI and web app for exporting feature layers, with
  support for pagination and filtering.

- chorokit: A Python helper that creates clean choropleth maps with defaults for
  projection, layout, legend and other key configurations.

This isn't a CNN project, but we can leverage /gis-datasets for mapping assets.
