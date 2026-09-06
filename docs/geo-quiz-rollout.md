# Geo quiz rollout

Geo quizzes are carousel posts with alternating prompt and answer slides. The default format is three countries per post.

## Format

- Slide 1: the cover. A world map behind the question, the difficulty, the country
  count and a request for a score in the comments.
- Slide 2: a highlighted country, no label.
- Slide 3: the same map with the country name and one short fact.
- Then a prompt and an answer per country.
- Last slide: the scorecard.

The cover is not optional. Opening on a map asks the viewer to work out what the
post is before deciding whether to stay. Override its headline with `cover_title`
in the batch config when a batch has a theme, such as island countries.

## Difficulty

- Easy: familiar outline, large country, common in school maps or news.
- Medium: recognizable outline but less obvious to a general audience.
- Hard: smaller country, similar neighbors or less familiar region.
- Expert: enclaves, microstates, unusual borders or countries often missed on blank maps.

Difficulty should reflect the audience, not geography trivia purity. If the map needs a hint to be fair, lower the difficulty or make it a themed post.

## Batch workflow

The country pool lives in `content/countries.csv`, not in this file. A
batch is a query against it, and rendering records which countries were used, so
the next batch does not repeat them.

```bash
uv run tiktoks quiz status              # pool depth per tier
uv run tiktoks quiz next --tier medium --count 3 --dry-run
uv run tiktoks quiz next --tier medium --count 3
```

That writes `posts/geo-quiz/geo-<tier>-NNN/quiz.yaml`, renders the slides and bumps
the usage counters. The batch config stays on disk as the record of what the post
contained, and can be edited before re-rendering.

1. Check the pool has depth in the tier you want.
2. Build the batch.
3. Check the contact sheet at thumbnail size.
4. Check every prompt slide for accidental hints from labels, neighboring shapes or framing.
5. Check every answer slide for legibility and spelling.
6. Keep a publish log with date, caption and any comments worth turning into a follow-up.

### Pool columns

`name` is what the answer slide says. `match_name` is the polygon to look up, and
is only needed when the two differ: the boundary file still calls Eswatini
"Swaziland". `center_lon`, `center_lat`, `zoom` and `context` override the default
framing. `times_used` and `last_rendered` are written by the renderer.

Selection is least-recently-used, recency first. Never-used countries come before
used ones, and a country posted last week sorts behind one posted twice a year ago.

Run `uv run tiktoks quiz status --validate` after editing the pool. It checks every
name against the boundary file, which is cheaper than a batch failing halfway
through a render.

Island nations and microstates need a `zoom` that pulls back far enough to show a
reference coastline, or the map is an unanswerable patch of ocean. Anything that
then covers too little of its window gets a locator ring automatically. Render a
new one and look at it before adding it to a batch.

## Country pools

The pools live in `content/countries.csv`, 25 countries per tier. Add rows there
rather than here, so `quiz status` can report depth and selection can avoid repeats.

At three countries a post, each tier holds roughly eight posts before it starts
repeating. `quiz status` is the signal for when to add more.

Difficulty should reflect the audience, not geography trivia purity. If the map
needs a hint to be fair, lower the difficulty or make it a themed post.

## QA checklist

The renderer already enforces the export size, the file naming and that nothing
lands under TikTok's interface. A batch that fails those does not finish. What is
left for a human:

- Prompt slide has no answer text.
- Answer slide names the country clearly and spells it right.
- Map does not crop the highlighted country.
- The country is findable. Tiny island nations get a locator ring; check it is
  centered on the right islands.
- Disputed borders render as disputed when they appear.
- The fact on the answer slide is true and worth reading.
