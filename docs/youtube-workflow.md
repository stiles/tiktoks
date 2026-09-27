# YouTube music and upload workflow

Music is part of the intended video. The default workflow selects a clean,
licensed track matched to the post's format; it never silently falls back to
silence. If no track is ready, preparation stops with an actionable error.

## Get a clean source recording

For Artlist, confirm your subscription includes stock music and covers the
intended channel/use, then download the full licensed track. Preview downloads
can contain a spoken watermark. Adding a channel to Clearlist does not remove
that watermark: replace the source file and rebuild the video. Save the track's
license certificate and add your channel to Clearlist while the subscription
is active. Confirm coverage for new publications before reusing a saved track.

[Artlist downloads](https://help.artlist.io/hc/en-us/articles/29596510418461-Downloading-Artlist-s-assets)
· [Clearlist](https://help.artlist.io/hc/en-us/articles/29648622402333-Understanding-Artlist-s-Clearlist)

For a free alternative, use music downloaded directly from YouTube Studio's
Audio Library. Save the track's license details and any required attribution.
CC BY and documented CC0 recordings are also supported. Rights must cover both
composition and recording; a public-domain composition alone is insufficient.
“Royalty free” does not mean public domain or guarantee against mistaken claims.

[YouTube Audio Library guidance](https://support.google.com/youtube/answer/3376882)

## Review and register the file

Listen to the entire downloaded file for speech, ads and preview watermarks.
Audition it against a representative video, then record the catalog metadata.
Two free candidates, `carefree` and `monkeys-spinning-monkeys`, have been
downloaded directly from Kevin MacLeod with CC BY 4.0 credits saved alongside
them. Local globe-quiz audition videos are in `review/free-music`. The user approved Carefree from the 45-second globe-quiz preview on September
27, 2026. Carefree is now the preferred geography-quiz track. Monkeys Spinning
Monkeys remains an unapproved alternative. Longer uses of Carefree should be
auditioned separately; the approval was for this preview. Do not mark a file reviewed solely from its filename or ID3 tags.

Example Artlist entry (placeholders must be replaced with actual evidence):

```yaml
  - slug: example-clean-bed
    file: example-clean-bed.wav
    title: Actual track title
    artist: Actual creator
    license: Artlist
    license_url: https://help.artlist.io/hc/en-us/articles/29490991524253-Understanding-Artlist-s-license
    source: https://example.org/replace-with-actual-track-page
    rights_verified: true
    license_evidence: path/to/saved-license-and-coverage-notes
    reviewed_clean: true
    sha256: replace-with-shasum-output
    formats: [geo-quiz]
```

Supported license labels: `Artlist`, `YouTube Audio Library`, `CC BY 3.0`,
`CC BY 4.0`, `CC0 1.0`. Artlist and YouTube Audio Library entries require
`rights_verified` and `license_evidence`; CC BY entries require `attribution`.
For an Audio Library track that requires credit, also save its full required
credit in `attribution`. Credits are included in the upload description.
Every track requires a source, license URL, clean-file review and checksum.
These fields record human verification; software cannot determine legal rights.

Compute the checksum after review with `shasum -a 256 content/audio/FILENAME`.
Changing the audio invalidates the review until the new file is checked.

Match the actual `format` from `post.json` after listening with the video:

| Video style | Music direction |
| --- | --- |
| Geography, flag and neighbor quizzes | Light instrumental pulse, playful, sparse melody |
| Mystery maps and progressive reveals | Restrained curiosity and tension, no dramatic stings |
| Data stories and comparisons | Neutral ambient or minimal electronic bed |
| Hard quizzes | Slower, sparse instrumental bed with room to think |

If several reviewed tracks match, the catalog default is preferred when it
matches the format; otherwise the first slug alphabetically is selected.
Use `--audio SLUG` to choose a different approved track.

## Prepare, preview, then upload

```bash
uv run tiktoks video --list-audio
uv run tiktoks video --dir posts/geo-quiz/geo-easy-001/night --audio YOUR_TRACK_SLUG
```

Play the resulting MP4 locally. Check the music level, reading time and reveal.
Then upload a private draft:

```bash
uv run tiktoks youtube upload --dir posts/geo-quiz/geo-easy-001/night
```

A supplied `--audio SLUG` rebuilds an existing MP4 before uploading, so a music
change actually reaches YouTube. Old or modified renders without verified
records must be rebuilt. `--silent` remains an explicit opt-in utility, not a
fallback or the recommended workflow.

Check the private draft in Studio, including copyright checks, and change its
visibility there. Running upload again creates another video, rather than
changing the existing video's visibility.

Ordinary YouTube ads are separate from embedded audio: music choice cannot
ensure ad-free playback. [YouTube's explanation](https://support.google.com/youtube/answer/2475463).
