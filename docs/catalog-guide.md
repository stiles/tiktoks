# Mystery-map catalog reference

Most guess-the-map ideas are one query each, so a post is a catalog entry rather than a hand-built CSV. Data is fetched, joined on ISO 3166-1 alpha-3 through `data/reference/country_crosswalk.csv`, and cached on disk.

Add entries under the top-level `posts:` list in `content/guess-map.yaml`.
This excerpt shows one existing entry; review its expectations and corrections
when reusing it.

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
- `include` and `exclude` correct known errors in the open. The catalog includes explicit corrections for kingdom-versus-country membership records and outdated membership statements. Recheck these when reviewing an entry; a passing count does not prove the membership is correct.

[Back to usage](../README.md#mystery-maps)
