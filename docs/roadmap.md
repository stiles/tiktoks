# Roadmap

## Measure what gets posted

TikTok analytics are a rolling window. The creator dashboard holds 60 days, and the API time series default to seven. Nothing backfills. If the collector is not running when a post goes out, that post's early hours are gone for good, and the early hours are the part worth reading.

So the collector comes before the posting schedule, not after it.

### What to pull

TikAPI's `GET /creator/analytics/{type}` is the useful one. It needs a creator or business account and an authorized session, and it takes a `days` window.

| Type | Returns |
| --- | --- |
| `overview` | `vv_history` views, `pv_history` profile views, like, comment and share history, `follower_num_history` |
| `content` | The same series broken out per post |
| `video` | One post, by `media_id`. Includes `video_finish_rate_history_7d` and `video_new_followers_history_7d` |
| `followers` | Follower counts and active hours |

Finish rate and new followers per post are the two that matter for this project. A quiz carousel lives or dies on whether people swipe to the end, and finish rate is the only number that says so. Views measure the thumbnail; finish rate measures the format.

`GET /public/posts` needs no authentication and returns per-post engagement counts for any account by `secUid`. Use it as a fallback and to track comparable accounts.

The official route is worse for this. TikTok's Content Posting API `/v2/video/query/` only returns metrics for posts published through the API, so manual uploads return nothing, and the Research API needs a separate approval.

### The join problem

Metrics are worthless without knowing which post they belong to. A rendered batch has a slug, a format and a difficulty; a TikTok post has an ID. Nothing connects them unless we write it down.

Keep `data/publish-log.csv`, one row per post, filled in at publish time:

```
post_id,url,posted_at,format,slug,difficulty,topic,slide_count,caption
```

That is what turns a pile of view counts into an answer to a real question: do expert quizzes hold people longer than easy ones, do US maps beat world maps, does the answer-in-comments variant get more comments than the answer-on-the-next-slide variant.

### Storage

Append-only daily snapshots, so deltas are computable and a bad pull never overwrites a good one:

```
data/metrics/snapshots/YYYY-MM-DD.csv
```

Small enough to keep in git. Mirror to S3 if it grows.

### Build order

1. `tiktoks metrics auth` to store the TikAPI account key in `.env`.
2. `tiktoks metrics pull` to write one dated snapshot.
3. A GitHub Action on a daily cron, same shape as the bots repo.
4. `tiktoks metrics report` to join snapshots against the publish log and rank formats by finish rate.

## Known gaps in the renderer

- Island chains such as the Maldives and Fiji read as specks at any honest zoom. They need an inset before they belong in the expert pool.
- The United States frames on the lower 48 plus Alaska, which leaves a lot of ocean. Works, but wants a `center` and `zoom` override.
- No disputed-boundary layer yet. `cnn-disputed-lines-50m.geojson` is loaded but never drawn. It matters on any map covering Kashmir, the Western Sahara or the Korean DMZ.
- No US state or county geography wired up, and much of the guess-the-map backlog is county level.
- Choropleth binning is quantiles only. Some measures want natural breaks or fixed thresholds.

## Formats not built yet

- Answer-in-comments variant for guess-the-map, which trades a reveal slide for comment volume.
- Intro slide for themed quiz batches, such as island countries or landlocked countries.
- Multi-slide stories, where one chart builds across several frames.
