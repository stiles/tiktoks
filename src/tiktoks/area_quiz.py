"""Two-choice land-area quizzes with equal-scale geographic reveals."""

from dataclasses import replace
from pathlib import Path

import numpy as np

from tiktoks.config import POSTS_DIR
from tiktoks.io import read_yaml
from tiktoks.maps import (
    MapView,
    draw_backdrop,
    draw_outline,
    prepare_outline,
    prepare_world,
    quiz_countries,
    world_countries,
)
from tiktoks.post import Post
from tiktoks.slides import Slide
from tiktoks.style import get_theme


def winner_index(choices: list[dict]) -> int:
    if len(choices) != 2:
        raise ValueError("Each area question requires two choices.")
    values = [float(c["land_km2"]) for c in choices]
    if not all(np.isfinite(v) and v > 0 for v in values):
        raise ValueError("Land areas must be finite and positive.")
    if values[0] == values[1]:
        raise ValueError("A tied pair needs a different question.")
    return int(values[1] > values[0])


def comparison_views(geography, choices: list[dict]) -> list[MapView]:
    """Center each equal-area projection; share bounds without resizing geometry."""
    targets = []
    for choice in choices:
        view = prepare_outline(geography, choice.get("match_name", choice["name"]))
        target = view.target.copy()
        x0, y0, x1, y1 = target.total_bounds
        target.geometry = target.geometry.translate(-(x0 + x1) / 2, -(y0 + y1) / 2)
        targets.append(target)
    width = max(t.total_bounds[2] - t.total_bounds[0] for t in targets) * 1.16
    height = max(t.total_bounds[3] - t.total_bounds[1] for t in targets) * 1.16
    bounds = (-width / 2, -height / 2, width / 2, height / 2)
    return [MapView(t, bounds, t) for t in targets]


def stack(slide, lines):
    slide.centered_stack(
        [
            {
                "text": text,
                "size": size,
                "min_size": 32,
                "max_lines": 3,
                "color": color,
                "weight": "bold" if size >= 46 else "normal",
                "gap_after": gap,
                "kind": f"quiz text {i}",
            }
            for i, (text, size, color, gap) in enumerate(lines)
        ]
    )


def render_area_quiz(config_path: str | Path, theme=None, *, output_dir=None) -> list[Path]:
    config_path = Path(config_path)
    config = read_yaml(config_path)
    theme = get_theme(theme)
    questions = config["questions"]
    if not questions:
        raise ValueError("An area quiz needs questions.")
    winners = [winner_index(q["choices"]) for q in questions]
    geography = quiz_countries()
    # Resolve all geometry before writing any slides.
    views = [comparison_views(geography, q["choices"]) for q in questions]
    year = config["year"]
    source = f"Land: World Bank / FAO, {year}"
    total = len(questions)
    post = Post(
        slug=config["slug"],
        format="area-quiz",
        theme=theme,
        output_dir=Path(output_dir or POSTS_DIR / "area-quiz" / config["slug"] / theme.name),
        title=config["title"],
        topic="country land area",
        config_path=config_path,
        caption=f"Which country has more land? {total} matchups. Choose A or B before "
        f"swiping. Land area excludes inland water. World Bank / FAO, {year}. "
        "Comment your score! #geography #quiz #maps",
        sources=[
            config["source_url"],
            config["source_definition"],
            "Outlines: Natural Earth 1:10 million; cover: CNN 1:50 million",
        ],
    )
    cover = Slide(theme, source=source)
    stack(
        cover,
        [
            ("LAND AREA QUIZ", 30, theme.highlight, 32),
            (config["title"], 72, theme.text, 42),
            (f"{total} matchups. Pick A or B.", 36, theme.text, 22),
            ("Land only. Lakes and rivers excluded.", 30, theme.muted, 24),
            ("Can you get a perfect score?", 32, theme.muted, 0),
        ],
    )
    ax, aspect = cover.backdrop_axes()
    draw_backdrop(ax, prepare_world(world_countries()), theme=theme, aspect=aspect, zoom=1.9)
    cover.scrim(0.22 if theme.name == "paper" else 0.3)
    post.add(cover, kind="cover", alt=f"{config['title']} {total} two-choice questions.")
    for index, (question, winner, pair_views) in enumerate(
        zip(questions, winners, views, strict=True), 1
    ):
        choices = question["choices"]
        prompt = Slide(
            theme, source=source, cue="Lock it in. Swipe for the answer", badge=f"{index}/{total}"
        )
        stack(
            prompt,
            [
                ("WHICH HAS MORE LAND?", 32, theme.muted, 62),
                (f"A: {choices[0]['name']}", 64, theme.text, 42),
                ("OR", 28, theme.muted, 42),
                (f"B: {choices[1]['name']}", 64, theme.text, 62),
                ("Land only. Lakes and rivers excluded.", 32, theme.muted, 0),
            ],
        )
        post.add(
            prompt,
            kind="prompt",
            alt=f"Which has more land? A: {choices[0]['name']}. B: {choices[1]['name']}.",
        )
        answer_theme = replace(theme, map_panel=False) if theme.name == "paper" else theme
        answer = Slide(
            answer_theme, source=source, badge=f"{index}/{total}", cue="One point if you got it"
        )
        answer.kicker(f"Answer: {'AB'[winner]} · Land area")
        answer.title(f"{choices[winner]['name']} has more land.")
        answer.dek(
            "\n".join(
                f"{'AB'[i]}: {c['name']}: {c['land_km2']:,.0f} km²" for i, c in enumerate(choices)
            )
        )
        ax, aspect = answer.map_axes()
        for i, view in enumerate(pair_views):
            panel = ax.inset_axes([0.02 + 0.5 * i, 0.1, 0.46, 0.75])
            draw_outline(
                panel,
                view,
                theme=theme,
                aspect=aspect * 0.46 / 0.75,
                color=theme.highlight if i == winner else theme.muted,
            )
            ax.text(
                0.25 + 0.5 * i,
                0.9,
                "AB"[i],
                transform=ax.transAxes,
                ha="center",
                color=theme.text,
                fontsize=26,
                weight="bold",
            )
        ax.text(
            0.5,
            0.035,
            "Same map scale. Outlines include inland water.",
            transform=ax.transAxes,
            ha="center",
            color=theme.muted,
            fontsize=16,
        )
        difference = (choices[winner]["land_km2"] / choices[1 - winner]["land_km2"] - 1) * 100
        post.add(
            answer,
            kind="answer",
            title=choices[winner]["name"],
            alt=f"{choices[winner]['name']} has {difference:.1f}% more land. "
            + "; ".join(f"{c['name']}: {c['land_km2']:,.0f} square kilometers" for c in choices)
            + ". Country outlines shown at the same map scale.",
        )
    score = Slide(theme, cue="Comment your score", badge=f"/{total}")
    stack(
        score,
        [
            ("HOW DID YOU DO?", 32, theme.highlight, 40),
            (f"{total} out of {total}?", 76, theme.text, 40),
            ("Which matchup surprised you?", 40, theme.text, 28),
            ("Tell us your score in the comments.", 32, theme.muted, 0),
        ],
    )
    post.add(score, kind="scorecard", alt=f"How many of the {total} questions did you get right?")
    post.finish()
    return post.paths
