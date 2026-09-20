# Know your neighbors — pilot 001

Six A/B questions, with text-only prompts and labeled regional answer maps.
Fourteen slides: cover, six question/answer pairs, scorecard. Labels use colons.
The correct choices are balanced across A and B without a fixed alternating pattern.

## Render

```bash
uv run tiktoks neighbors-quiz --config content/neighbors-quiz/neighbors-001/quiz.yaml --theme paper
uv run tiktoks neighbors-quiz --config content/neighbors-quiz/neighbors-001/quiz.yaml --theme night
make neighbors-quiz SLUG=neighbors-001 THEME=paper
```

`night` is the default; `paper` and `poster` are also accepted. Outputs go to
`posts/neighbors-quiz/neighbors-001/<theme>/`, including the contact sheet,
1080x1920 PNGs, and `post.json`. Rendered variants coexist.

```bash
uv run tiktoks stage --dir posts/neighbors-quiz/neighbors-001/paper --open
uv run tiktoks video --dir posts/neighbors-quiz/neighbors-001/night
```

## Evidence and scope

Ian Coleman's November 30, 2020 Factbook snapshot supplied the leads.
`factbook-excerpts.json` preserves the relevant fields and original archived
source links. The archive is not presented as current data.

The answer claims were cross-checked September 20, 2026 against these sources;
URLs and short source labels are also stored per question in `quiz.yaml`.
Verification means checking the currently available page, not that every page
was published in 2026.

| Question | Answer and evidence | Verification source |
| --- | --- | --- |
| Entirely surrounded by South Africa | Lesotho is an enclave inside South Africa. | [Australian DFAT](https://www.dfat.gov.au/geo/lesotho) |
| More land neighbors | Austria has eight; Switzerland has five. Count countries, not separate border segments. | [Austrian foreign ministry](https://www.bmeia.gv.at/oev-wien/about-austria/geography), [swisstopo](https://www.swisstopo.admin.ch/en/national-border) |
| Only neighbors are China and Russia | Mongolia's national atlas identifies both sides of its international boundary. | [Mongolia National Digital Atlas](https://www.mongolianatlas.ac.mn/en/atlas/general) |
| No border with Brazil | Brazil's neighbor list includes Peru and excludes Chile. | [IBGE](https://educa.ibge.gov.br/jovens/conheca-o-brasil/territorio/20591-introducao.html) |
| Doubly landlocked | Uzbekistan is landlocked and surrounded by landlocked countries. | [World Bank](https://www.worldbank.org/ext/en/country/uzbekistan) |
| Landlocked, with a Caspian shore | Kazakhstan has Caspian ports but no ocean coast. The Caspian is an inland basin; “no natural ocean outlet” avoids implying that navigation canals do not exist. | [Kazakhstan government](https://www.gov.kz/article/19305?lang=en), [Caspian description](https://oq.gov.kz/en/abai/kaspiy-tenhizi) |

## Visual treatment

Answers use Natural Earth 10m country geometry projected around the region.
Highlight marks the answer country; an accent marks a comparison/context country
when useful (Switzerland and Brazil). Cover geometry remains 50m.
Unlike the isolated area-comparison silhouettes, these are geographic regional
maps: blue areas in paper mode denote actual water. Country labels and framing
are curated per question. No labels or answer maps appear on prompts.

## Another batch

Copy the config to a new slug under `content/neighbors-quiz/`. Each question needs
`prompt`, exactly two distinct `choices`, an explicit `answer` of A or B,
`explanation`, `source_label`, verification `sources`, and a `map` specification.
Record the new verification date and supporting evidence. The renderer validates
structure; it cannot determine whether a manually entered answer is factually correct.

Map specs have regional `[west, south, east, north]` bounds, `highlight` country
names, optional `secondary` names, and labels with `text`, `lon`, `lat`, plus an
optional rotation. Keep label text inside the map and inspect every output for
collisions: the automatic slide layout check does not check geographic labels.
These regional bounds do not support crossing the antimeridian.

This is a curated format, not a random Factbook generator. It does not alter the
geo-quiz country pool or usage counts. `make rebuild` does not yet include this
format; use the explicit rendering commands above.
