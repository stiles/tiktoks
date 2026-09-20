# Factbook quiz ideas

The first [Know your neighbors pilot](../content/neighbors-quiz/neighbors-001/README.md)
is implemented as `neighbors-quiz`, with six questions verified against additional
sources and rendered as A/B prompts with regional answer maps.

## Source audit

Inspected September 20, 2026: [Ian Coleman's JSON archive](https://raw.githubusercontent.com/iancoleman/cia_world_factbook_api/refs/heads/master/data/factbook.json).
The file metadata gives a snapshot date of **2020-11-30**, parsed on
**2020-12-02**, with parser version `0.0.4-beta`. The repository's “latest” label
is not evidence that the contents are current.

There are 259 entries, including countries, territories, oceans and a World
aggregate. Do not treat that as 259 sovereign countries. Each entry wraps `data`
and `metadata`; the latter includes a dated archived CIA source URL.

Local research copies (ignored by Git):

- `data/reference/factbook/factbook-2020-11-30.json`
- `data/reference/factbook/inventory.json` — retrieval date, SHA-256 and field inventory

Use this archive to discover candidates. The ideas below are grounded in its
contents, but are not a current, publication-verified question bank. Retrieve the
original entry and verify the specific claim before producing a quiz.

## Candidate questions

Paths below are relative to `countries.<country_key>.data`.

| Question idea | Archive-supported answer or lead | Fields to mine | Visual reveal |
| --- | --- | --- | --- |
| Which country is completely surrounded by South Africa? | Lesotho | `geography.location`, `geography.land_boundaries.border_countries` | Zoom out from Lesotho to South Africa |
| Which has a higher lowest point: Lesotho or Nepal? | Lesotho: 1,400 m versus Nepal: 70 m | `geography.elevation.lowest_point.elevation.value` | Two labeled elevations; explain that this is the lowest point, not the tallest mountain |
| Which has higher average elevation: Mongolia or Austria? | Mongolia: 1,528 m versus Austria: 910 m | `geography.elevation.mean_elevation.value` | Terrain map and two bars |
| Which has more land neighbors: Austria or Switzerland? | Austria: 8 versus Switzerland: 5 in the archive | `geography.land_boundaries.border_countries` | Reveal and count named neighbors |
| Which two countries border Mongolia? | China and Russia | `geography.land_boundaries.border_countries` | Add its two neighbors after the guess |
| Which does Brazil NOT border: Peru or Chile? | Chile; Peru is in its border list | `geography.land_boundaries.border_countries` | Regional map with the actual border highlighted |
| Which is doubly landlocked: Uzbekistan or Mongolia? | Uzbekistan; Liechtenstein is another candidate | `geography.coastline.note`, neighbor lists | Two rings of neighbors; explain the need to cross at least two borders to reach an ocean |
| Which has a lower lowest point: Kazakhstan or the Netherlands? | Kazakhstan: −132 m versus the Netherlands: −7 m | `geography.elevation.lowest_point` | Below-sea-level comparison |
| Which has a higher peak: Canada or Switzerland? | Canada: 5,959 m versus Switzerland: 4,634 m | `geography.elevation.highest_point` | Named mountain silhouettes or an elevation chart |
| Which country takes its name from a tree? | Brazil; its country-name entry points to brazilwood | `government.country_name.etymology` | Country reveal with a short explanation |
| Which country has a larger share of its area recorded as water? | Derive `water / total`, with one source and territorial definition | `geography.area.water.value`, `geography.area.total.value` | Split bars; say “share,” not “amount” |
| Name a landlocked country that borders the Caspian Sea. | Kazakhstan is a documented candidate | `geography.coastline.note`, `geography.location` | Map explaining why an inland sea does not give ocean access |

## Best first series

**Know your neighbors** has the clearest visual payoff and needs little new data
presentation machinery. A six-question draft could use Lesotho, Austria versus
Switzerland, Mongolia's neighbors, Brazil versus Chile/Peru, Uzbekistan's double
landlocked status, and Kazakhstan's Caspian shore. Mix A/B and multiple-choice
formats only if the rules remain clear; for a first production batch, convert
these to consistently worded A/B questions.

**Highs and lows** is a second strong series: average elevation, highest point,
and lowest point. Name the metric in every prompt and answer. “Which country is
higher?” is too ambiguous, just as “larger” obscures land versus total area.

## What needs extra work

- **Equator crossings:** country coordinates are representative locations, not
  boundary extents. A northern latitude does not mean the country's land never
  crosses the equator. Use the boundary polygons to test land intersection with
  latitude zero, then verify island and territorial edge cases. Distinguish land
  crossed by the equator from territorial waters crossed by it.
- **Density:** derive population divided by land area only with aligned dates and
  geographic coverage. Prefer refreshed population figures, such as the existing
  World Bank pipeline. Do not present an archive-derived density as today's value.
- **Forest cover, GDP, population and similar statistics:** the snapshot date is
  not the observation year. For example, several land-use entries inspected here
  carry 2011 dates. Refresh these before making comparative questions.
- **Border counts:** normalize distinct countries before counting. China lists
  Russia twice, as northeast and northwest segments. France's list is scoped to
  metropolitan neighbors while Brazil's includes French Guiana. Define territorial
  scope explicitly. Verify current borders rather than freezing a 2020 list.
- **Elevation:** fields can be objects or strings. Ecuador's highest-point field
  is free text. Peak heights and names can also be revised. Check units and the
  original source; never silently coerce missing fields to zero.
- **Coastline length:** measurements depend on detail and conventions. It can
  generate leads, but is a weaker choice for close A/B comparisons.
- **Rankings:** the archive includes aggregates and dependencies. Recompute ranks
  after choosing the eligible country set; don't reuse `global_rank` blindly.

## Suggested question-bank record

Keep the prompt, options, answer, metric definition, country keys, exact JSON
field paths, archive date, observation date (if present), original source URLs,
verification source/date, explanation and proposed visual together. Only questions
with a completed current-source check should move into a rendering config.

The current `area-quiz` renderer remains specific to land area. These notes do not
change its source or quietly replace its verified World Bank values with Factbook
figures. Borders now have a dedicated `neighbors-quiz` renderer; an elevation
quiz would still need its own metric-aware rendering support.
