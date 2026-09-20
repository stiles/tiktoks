# Visual style

This project style borrows from newsroom habits: clear hierarchy, honest scales, direct labels and restrained color.

`night` is the default theme. `paper` and `poster` stay in `src/tiktoks/style.py` as alternates and as a way to check that a layout holds up under a different type scale. Run `make styles` to render all three against the same test slides.

## Canvas

- Every export is `1080x1920`. `validate_exports` fails the render if one is not.
- Margins are `88px` on the sides, `120px` at the top and `130px` at the bottom.
- Build for a phone preview first. Desktop review catches syntax problems, not thumb-stop problems.

## Layout

A slide stacks blocks from the top and the footer from the bottom, and the map takes whatever is left. Nothing is positioned by hand.

- Kicker, then title, then dek, then map.
- Source sits at the bottom, with an optional call-to-action pill above it and a difficulty badge in the top right.
- A prompt and its answer share one map rect, so the swipe reads as a reveal instead of a jump. `shared_slot()` works out the largest box that fits both, and never returns more than the space actually left, so the map cannot cover the legend or the source line.
- A map is scaled to fit its slot on both axes. A slot shorter than the data shrinks the map rather than cropping it.
- World maps trim a little of the empty Pacific rather than framing to the antimeridian. Judge that trade in rendered pixels, not in shares of a country: everything currently clipped covers under 40 square pixels on screen, while New Zealand and the United States stay whole.
- Keep the title on a guess-map slide to two lines. The map is the payoff, and a three-line headline at full size takes most of its room.
- Titles wrap against measured glyph widths and shrink until they fit the line budget. Do not wrap by character count; a 24-character line at 78pt runs off the canvas.

Set `hero=True` on a title when the slide carries a world map. A world map is 2.25:1 and fills less than half the frame, so the headline takes the top third.

## Type

- Avenir Next, falling back to Helvetica Neue and Arial.
- Sentence case, short headlines, a direct question on quiz prompts.
- One short fact on answer slides.
- Avoid rotated labels and dense legends.
- For A/B country comparisons, use `A: Country` and `B: Country` on both prompt
  and answer slides. Do not use bullets or middle dots between the letter and name.

## Color

The `night` theme:

- Background: `#14171c`.
- Text: `#f4f2ee`.
- Muted text: `#949ba6`.
- Land: `#333c47`.
- Water: `#181d24`.
- Borders: `#62707e`.
- Highlight: `#4fd1c5`.
- Accent, used for the call-to-action pill: `#f6a623`.
- No data: `#242a32`.

Difficulty sets the highlight and badge color: teal for easy, blue for medium, amber for hard, red for expert.

Use one strong color per slide unless color encodes a real category. A single-measure bar chart stays one color.

For area-comparison answers in `paper`, place the isolated country outlines
directly on the cream background, without a blue panel or border. Blue behind
unlocated silhouettes reads as water. Highlight the winner and mute the other
country. This treatment is specific to comparisons; regional maps still use
water to provide geographic context.

## Country comparison quizzes

Prompts show the question and two named choices, without maps or values. Answer
slides identify the winning letter and country, show both values with units, and
reveal the maps. Keep both answer maps at the same scale using equal-area
projections; do not independently enlarge each outline to fill its panel.

For land-area questions, state that inland water is excluded from the figures.
Use “has more land” rather than “is larger” in answer headlines, and repeat the
land-only definition on each prompt so the metric survives screenshots and sharing.
The outlines include inland water, so retain the explanatory map note and use
the sourced figures to determine the winner. Put the data source and year on
the slides and retain the full source details beside the quiz config.

## Maps

Projection is not optional. Plain lat/lon stretches anything above about 40 degrees and makes Canada and Russia the wrong shape.

- Country zooms use Lambert azimuthal equal area centered on the country.
- World maps use Equal Earth, with Antarctica dropped.
- Framing fills the map box rather than letterboxing inside it.
- The window is about four times the width of the country, floored at 250km and capped at 1,100km, so a microstate keeps some neighboring land and a small country does not become a dot.
- Distant outlying territory draws but does not set the window. Natural Earth folds Easter Island into Chile and French Guiana into France, and framing on the full extent would zoom out to an ocean.
- Highlighted countries take one fill with a dark rim. A light rim fringes every island and wrecks a coastline like Canada's.
- Disputed borders should be dotted or otherwise distinct when they matter.
- Avoid decorative shadows, glows and gradients.

Match a country by its `name`, not its `sovereignt`. Falling through to `sovereignt` returns the Falklands and Pitcairn alongside Britain.

Island chains such as the Maldives and Fiji still read as specks at any honest zoom. They need an inset before they are worth posting.

## Choropleths

- Use 5 to 7 bins. The default is 6.
- One hue, with lightness carrying the value: light for low, dark for high. Two
  hues make a reader hunt for a category boundary that is not there.
- Ramps live in `src/tiktoks/palettes.py`, from ColorBrewer. Pick one per map with
  `palette:` in the catalog entry and match it to the subject where there is an
  obvious fit, such as Greens for forest cover.
- The ramp should still read low-to-high in grayscale.
- Keep gray outside the scale for missing data, and label the no-data chip in the
  legend.
- Do not use rainbow scales.
- On a dark background a light-to-dark ramp inverts the emphasis: the low values
  glow and the high values sink into the slide. Render choropleths on `paper`
  unless there is a reason not to.

## Source lines

Data maps need a source line. Quiz maps should include a boundary source unless the caption carries it.

Keep source lines short:

`Boundaries: Natural Earth`

For data:

`Source: World Bank GDP per capita data; Natural Earth boundaries.`

## QA before posting

Render a contact sheet with `contact_sheet()` and check the batch at thumbnail size before opening any single slide.

- Confirm all text stays inside the margins.
- Confirm the answer is not visible on prompt slides.
- Confirm the prompt and answer maps sit in the same place.
- Confirm no country is framed on an outlying island instead of its mainland.
- Confirm the map still reads in grayscale.
- Confirm every data value has a source.
