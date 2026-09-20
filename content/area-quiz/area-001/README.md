# Land-area quiz pilot

Six A/B comparisons, using the World Bank's FAO-sourced 2023 land-area indicator
`AG.LND.TOTL.K2`. Land area excludes inland water bodies. Values in `quiz.yaml`
are the unrounded API values; slides round to whole square kilometers. Answers
are computed from the stored values, not the map polygons.

`source.json` is the saved API response retrieved September 20, 2026:
https://api.worldbank.org/v2/country/ITA;JPN;ESP;EGY;DEU;FIN;KAZ;ARG;COD;DZA;CHN;CAN/indicator/AG.LND.TOTL.K2?date=2023&format=json&per_page=100

Definition: https://databank.worldbank.org/metadataglossary/world-development-indicators/series/AG.LND.TOTL.K2

Natural Earth outlines are projected in meters with country-centered equal-area
projections. Both answer panels share a map scale; neither outline is independently
resized. Outlines include inland water, so use the printed land figures for the
comparison. Country geometry and statistical territorial coverage may differ.

## Format and styling

The six-question pilot has 14 slides: a cover, six prompt/answer pairs and a
scorecard. Prompts show two country names without maps or values, so the graphics
cannot give away the answer. Use colons for choices: `A: Italy` and `B: Japan`.
Answer slides retain those labels, identify the winner, give both land areas and
show the outlines at the same map scale.
Use “has more land” in answer headlines, not “is larger.” Repeat the land-only
definition on each prompt. Canada exceeds China by total area, while China has
more land in this dataset; generic size wording obscures that distinction.

In paper mode, comparison outlines sit directly on the cream page. Do not place
them on a blue rectangle or add a panel border: that suggests a shared body of
water. The winner uses the theme highlight; the other country uses muted color.
The map note states that outlines include inland water; the land-area figures
exclude it. Question numbering and the final score are derived from the config.

## Render and review

Render from the repository root:

```bash
uv run tiktoks area-quiz --config content/area-quiz/area-001/quiz.yaml --theme night
uv run tiktoks area-quiz --config content/area-quiz/area-001/quiz.yaml --theme paper
```

All three themes (`night`, `paper`, `poster`) are supported; `night` is the default.
The shortcut `make area-quiz SLUG=area-001 THEME=night` renders the same batch.
Outputs go to `posts/area-quiz/area-001/<theme>/`, including the contact sheet and
platform-ready manifest. Review the contact sheet, then stage with:

```bash
uv run tiktoks stage --dir posts/area-quiz/area-001/paper --open
```

`make rebuild` currently covers geography batches and the guess-map catalog; run
the explicit `area-quiz` command above to rebuild this pilot.

## Make another batch

Copy this directory to a new slug under `content/area-quiz/`. Update `slug` and
`title` in `quiz.yaml`, then curate `questions`, each with exactly two `choices`.
Each choice has a display `name`, `iso3`, and numeric `land_km2`; use `match_name`
when the geometry's name differs (for example, `Dem. Rep. Congo` for `DR Congo`).
Array order determines A and B. The renderer computes the winner and rejects
ties, nonpositive values and nonfinite values.

Use one source and year across the batch. Save the supporting response in
`source.json`, update `year`, `indicator`, `source_url`, and `source_definition`,
and record the retrieval date and API URL here. Preserve unrounded values in the
config; the slides format them as whole square kilometers. This renderer is for
land area; changing the indicator alone does not make it a population or density quiz.

Before rendering a new batch, verify its values against the saved response and
check that every country resolves to the intended geometry. After rendering,
check every A/B label, winner, source year, same-scale outline and text layout.
Compare close matchups carefully and avoid territorial coverage differences that
would make a result misleading. Quiz generation is manual; it does not draw from
or update `content/countries.csv`.
