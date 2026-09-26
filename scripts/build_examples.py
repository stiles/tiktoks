"""Refresh the documentation gallery from existing local slide renders."""

import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/examples"
# title, rendered directory, slide indices, description, command
EXAMPLES = [
    (
        "Globe quiz",
        "geo-quiz/geo-globe-hard-001/night",
        [2, 3],
        "Name the country in red on a globe, then swipe for the answer. Country "
        "selection follows the requested difficulty tier.",
        "make quiz-globe TIER=hard COUNT=3",
    ),
    (
        "Progressive quiz",
        "geo-quiz/geo-progressive-hard-001/night",
        [2, 3, 4],
        "A tight prompt, a wider hint and the answer. Country selection and framing "
        "both follow the difficulty tier.",
        "make quiz-progressive TIER=hard COUNT=3",
    ),
    (
        "Classic geography quiz",
        "geo-quiz/geo-medium-001/night",
        [2, 3],
        "Identify the highlighted country with neighboring borders visible, then "
        "reveal its name and a fact.",
        "make quiz TIER=medium COUNT=3",
    ),
    (
        "Silhouette quiz",
        "geo-quiz/geo-silhouette-hard-001/night",
        [2, 3],
        "Country shapes and surrounding land without neighboring borders. This "
        "variant draws from the whole pool; difficulty controls the amount of context.",
        "make quiz-silhouette TIER=hard COUNT=3",
    ),
    (
        "Master outline quiz",
        "geo-quiz/geo-master-001/night",
        [2, 3],
        "An isolated outline with no surrounding land. The answer restores regional "
        "context. Candidates come from the expert pool.",
        "make quiz TIER=master COUNT=3",
    ),
    (
        "Land-area comparison",
        "area-quiz/area-001/night",
        [2, 3],
        "Choose which country has more land, then compare outlines drawn at the same scale.",
        "make area-quiz",
    ),
    (
        "Neighbors quiz",
        "neighbors-quiz/neighbors-001/paper",
        [2, 3],
        "An A/B question about borders, followed by a labeled map explanation. This "
        "example uses the paper theme.",
        "make neighbors-quiz THEME=paper",
    ),
    (
        "Mystery map",
        "guess-map/nato-members/night",
        [1, 2],
        "Guess what the highlighted countries have in common, then reveal the grouping.",
        "uv run tiktoks catalog --slug nato-members",
    ),
    (
        "Data story",
        "stories/2026-ssa-name-karen",
        [1, 2, 3],
        "The opening three slides of a story about the name Karen, built from Social "
        "Security baby-name data.",
        "make karen",
    ),
]


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    sections = [
        "# Examples\n\n"
        "A gallery of rendered posts for TikTok carousels and YouTube Shorts. "
        "These are selected slide sequences, read left to right, rather than full posts. "
        "Click a preview to enlarge it.\n\n"
        "[Setup and all commands](README.md#setup) · "
        "[Geography quiz guide](docs/geo-quiz-rollout.md)\n\n"
        "The commands below create or render examples after setup. "
        "Commands that select a new quiz batch rotate countries, so your picks may differ."
    ]
    for title, directory, indices, description, command in EXAMPLES:
        source = ROOT / "posts" / directory
        manifest = json.loads((source / "post.json").read_text())
        records = [manifest["slides"][i - 1] for i in indices]
        width, height, gap = 360, 640, 12
        preview = Image.new(
            "RGB", (width * len(records) + gap * (len(records) - 1), height), "#ddd9d2"
        )
        for i, record in enumerate(records):
            with Image.open(source / record["file"]) as slide:
                preview.paste(
                    slide.convert("RGB").resize((width, height), Image.Resampling.LANCZOS),
                    (i * (width + gap), 0),
                )
        filename = title.lower().replace(" ", "-") + ".jpg"
        preview.save(OUTPUT / filename, quality=88, optimize=True)
        image_path = f"docs/examples/{filename}"
        alt = (
            " / ".join(record["alt"] for record in records)
            .replace("[", "(")
            .replace("]", ")")
            .replace("\n", " ")
        )
        sections.append(
            f"## {title}\n\n{description}\n\n"
            f"[![{alt}]({image_path})]({image_path})\n\n"
            f"```bash\n{command}\n```\n\n"
            f"[Sample metadata](posts/{directory}/post.json)"
        )
    sections.append(
        "## Refreshing the gallery\n\n"
        "The compact JPEG previews in `docs/examples/` are versioned so this page works "
        "on GitHub without downloading or rendering the full posts. Full-size slide exports "
        "remain ignored. After rendering the sample posts listed in "
        "[the gallery script](scripts/build_examples.py), refresh the previews and "
        "this page with:\n\n"
        "```bash\nuv run python scripts/build_examples.py\n```"
    )
    (ROOT / "EXAMPLES.md").write_text("\n\n".join(sections) + "\n")
    print(f"Wrote {len(EXAMPLES)} gallery previews and EXAMPLES.md")


if __name__ == "__main__":
    main()
