# Examples

A gallery of rendered posts for TikTok carousels and YouTube Shorts. These are selected slide sequences, read left to right, rather than full posts. Click a preview to enlarge it.

[Setup and all commands](README.md#setup) · [Geography quiz guide](docs/geo-quiz-rollout.md)

The commands below create or render examples after setup. Commands that select a new quiz batch rotate countries, so your picks may differ.

## Globe quiz

Name the country in red on a globe, then swipe for the answer. Country selection follows the requested difficulty tier.

[![An unlabeled globe with one country highlighted in red. / Zimbabwe highlighted in red on a globe.](docs/examples/globe-quiz.jpg)](docs/examples/globe-quiz.jpg)

```bash
make quiz-globe TIER=hard COUNT=3
```

[Sample metadata](posts/geo-quiz/geo-globe-hard-001/night/post.json)

## Progressive quiz

A tight prompt, a wider hint and the answer. Country selection and framing both follow the difficulty tier.

[![A regional map with one unlabeled country highlighted. / A regional map with one unlabeled country highlighted in a wider view. / A regional map with Iran highlighted and named. It bridges the Persian Gulf and the Caspian world between the Middle East and Central Asia.](docs/examples/progressive-quiz.jpg)](docs/examples/progressive-quiz.jpg)

```bash
make quiz-progressive TIER=hard COUNT=3
```

[Sample metadata](posts/geo-quiz/geo-progressive-hard-001/night/post.json)

## Classic geography quiz

Identify the highlighted country with neighboring borders visible, then reveal its name and a fact.

[![A regional map with one unlabeled country highlighted. / A regional map with Chile highlighted and named. A long, narrow country pressed between the Andes and the Pacific.](docs/examples/classic-geography-quiz.jpg)](docs/examples/classic-geography-quiz.jpg)

```bash
make quiz TIER=medium COUNT=3
```

[Sample metadata](posts/geo-quiz/geo-medium-001/night/post.json)

## Silhouette quiz

Country shapes and surrounding land without neighboring borders. This variant draws from the whole pool; difficulty controls the amount of context.

[![A regional map with one unlabeled country highlighted. / A regional map with Kenya highlighted and named. The equator runs through it, just north of Nairobi.](docs/examples/silhouette-quiz.jpg)](docs/examples/silhouette-quiz.jpg)

```bash
make quiz-silhouette TIER=hard COUNT=3
```

[Sample metadata](posts/geo-quiz/geo-silhouette-hard-001/night/post.json)

## Master outline quiz

An isolated outline with no surrounding land. The answer restores regional context. Candidates come from the expert pool.

[![An unlabeled country outline, north up, with no surrounding land. / A regional map with Guinea-Bissau highlighted and named. A small West African country with a ragged Atlantic coastline.](docs/examples/master-outline-quiz.jpg)](docs/examples/master-outline-quiz.jpg)

```bash
make quiz TIER=master COUNT=3
```

[Sample metadata](posts/geo-quiz/geo-master-001/night/post.json)

## Land-area comparison

Choose which country has more land, then compare outlines drawn at the same scale.

[![Which has more land? A: Italy. B: Japan. / Japan has 23.3% more land. Italy: 295,720 square kilometers; Japan: 364,569 square kilometers. Country outlines shown at the same map scale.](docs/examples/land-area-comparison.jpg)](docs/examples/land-area-comparison.jpg)

```bash
make area-quiz
```

[Sample metadata](posts/area-quiz/area-001/night/post.json)

## Neighbors quiz

An A/B question about borders, followed by a labeled map explanation. This example uses the paper theme.

[![Which country is entirely surrounded by South Africa? A: Eswatini. B: Lesotho. / B: Lesotho. Lesotho's only neighbor is South Africa. Regional map with South Africa, Lesotho, Eswatini labeled.](docs/examples/neighbors-quiz.jpg)](docs/examples/neighbors-quiz.jpg)

```bash
make neighbors-quiz THEME=paper
```

[Sample metadata](posts/neighbors-quiz/neighbors-001/paper/post.json)

## Mystery map

Guess what the highlighted countries have in common, then reveal the grouping.

[![An unlabeled world map with countries shaded. The subject is not named. / A map. They are NATO members. NATO has 32 members. Finland joined in 2023 and Sweden in 2024.](docs/examples/mystery-map.jpg)](docs/examples/mystery-map.jpg)

```bash
uv run tiktoks catalog --slug nato-members
```

[Sample metadata](posts/guess-map/nato-members/night/post.json)

## Data story

The opening three slides of a story about the name Karen, built from Social Security baby-name data.

[![A title slide about the baby name Karen. / A line chart of the baby name Karen, rising to its peak year 1956. / A line chart of the baby name Karen through 2010.](docs/examples/data-story.jpg)](docs/examples/data-story.jpg)

```bash
make karen
```

[Sample metadata](posts/stories/2026-ssa-name-karen/post.json)

## Refreshing the gallery

The compact JPEG previews in `docs/examples/` are versioned so this page works on GitHub without downloading or rendering the full posts. Full-size slide exports remain ignored. After rendering the sample posts listed in [the gallery script](scripts/build_examples.py), refresh the previews and this page with:

```bash
uv run python scripts/build_examples.py
```
