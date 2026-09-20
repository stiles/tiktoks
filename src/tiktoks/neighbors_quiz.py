"""Curated A/B geography questions with labeled regional answer maps."""

from pathlib import Path

import geopandas as gpd
import matplotlib.patheffects as pe
from shapely.geometry import Point, box

from tiktoks.area_quiz import stack
from tiktoks.config import POSTS_DIR
from tiktoks.io import read_yaml
from tiktoks.maps import (
    MapView,
    country_match,
    draw_backdrop,
    draw_highlight,
    frame_axes,
    laea_crs,
    near_center,
    prepare_world,
    quiz_countries,
    world_countries,
)
from tiktoks.post import Post
from tiktoks.slides import Slide
from tiktoks.style import get_theme


def validate_question(question):
    choices = question["choices"]
    if len(choices) != 2 or len(set(choices)) != 2:
        raise ValueError("Each question needs two distinct choices.")
    if question["answer"] not in ("A", "B"):
        raise ValueError("Answer must be A or B.")
    if not question.get("sources") or not question.get("explanation"):
        raise ValueError("Every answer needs sources and an explanation.")
    return choices["AB".index(question["answer"])]


def regional_view(geography, spec):
    west, south, east, north = spec["bounds"]
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Invalid regional bounds.")
    center = ((west + east) / 2, (south + north) / 2)
    crs = laea_crs(*center)
    frame = gpd.GeoSeries([box(west, south, east, north).segmentize(1)], crs="EPSG:4326")
    bounds = tuple(frame.to_crs(crs).total_bounds)
    base = near_center(geography, center).to_crs(crs)
    target = country_match(geography, spec["highlight"]).to_crs(crs)
    if spec.get("secondary"):
        country_match(geography, spec["secondary"])
    return MapView(base, bounds, target, crs=crs)


def draw_reveal(ax, aspect, view, spec, geography, theme):
    draw_highlight(ax, view, theme=theme, aspect=aspect, locator=False)
    if spec.get("secondary"):
        country_match(geography, spec["secondary"]).to_crs(view.crs).plot(
            ax=ax, color=theme.accent, edgecolor=theme.border, linewidth=0.6
        )
        frame_axes(ax, view.bounds, aspect)
    for label in spec.get("labels", []):
        point = (
            gpd.GeoSeries([Point(label["lon"], label["lat"])], crs="EPSG:4326")
            .to_crs(view.crs)
            .iloc[0]
        )
        ax.text(
            point.x,
            point.y,
            label["text"],
            ha="center",
            va="center",
            fontsize=16,
            color=theme.text,
            weight="bold",
            clip_on=True,
            rotation=label.get("rotation", 0),
            path_effects=[pe.withStroke(linewidth=3, foreground=theme.background)],
        )


def render_neighbors_quiz(config_path, theme=None, *, output_dir=None):
    config_path = Path(config_path)
    config = read_yaml(config_path)
    theme = get_theme(theme)
    questions = config["questions"]
    if not questions:
        raise ValueError("A neighbors quiz needs questions.")
    answers = [validate_question(q) for q in questions]
    geography = quiz_countries()
    views = [regional_view(geography, q["map"]) for q in questions]
    total = len(questions)
    sources = list(dict.fromkeys(url for q in questions for url in q["sources"]))
    post = Post(
        slug=config["slug"],
        format="neighbors-quiz",
        theme=theme,
        output_dir=Path(output_dir or POSTS_DIR / "neighbors-quiz" / config["slug"] / theme.name),
        title=config["title"],
        topic="borders and landlocked countries",
        config_path=config_path,
        sources=sources + ["Maps: Natural Earth 1:10 million; cover: CNN 1:50 million"],
        caption=f"Know your neighbors. {total} geography questions. Pick A or B before "
        "swiping for the map reveal. How many did you get? #geography #quiz #maps",
    )
    cover = Slide(theme, source="Maps: Natural Earth")
    stack(
        cover,
        [
            ("BORDERS QUIZ", 30, theme.highlight, 32),
            (config["title"], 76, theme.text, 42),
            (f"{total} questions. Pick A or B.", 36, theme.text, 30),
            ("The map reveals the answer.", 32, theme.muted, 0),
        ],
    )
    ax, aspect = cover.backdrop_axes()
    draw_backdrop(ax, prepare_world(world_countries()), theme=theme, aspect=aspect, zoom=1.9)
    cover.scrim(0.22 if theme.name == "paper" else 0.3)
    post.add(cover, kind="cover", alt=f"{config['title']} {total} A/B geography questions.")
    for i, (q, answer_name, view) in enumerate(zip(questions, answers, views, strict=True), 1):
        prompt = Slide(theme, badge=f"{i}/{total}", cue="Lock it in. Swipe for the map")
        stack(
            prompt,
            [
                (q["prompt"], 52, theme.text, 60),
                (f"A: {q['choices'][0]}", 58, theme.text, 32),
                ("OR", 28, theme.muted, 32),
                (f"B: {q['choices'][1]}", 58, theme.text, 0),
            ],
        )
        post.add(
            prompt, kind="prompt", alt=f"{q['prompt']} A: {q['choices'][0]}. B: {q['choices'][1]}."
        )
        answer = Slide(
            theme,
            badge=f"{i}/{total}",
            cue="One point if you got it",
            source=q["source_label"] + "\nMap: Natural Earth",
        )
        answer.kicker(f"Answer: {q['answer']}")
        answer.title(answer_name)
        answer.dek(q["explanation"])
        ax, aspect = answer.map_axes()
        draw_reveal(ax, aspect, view, q["map"], geography, theme)
        post.add(
            answer,
            kind="answer",
            title=answer_name,
            alt=f"{q['answer']}: {answer_name}. {q['explanation']} Regional map with "
            + ", ".join(label["text"] for label in q["map"].get("labels", []))
            + " labeled.",
        )
    score = Slide(theme, cue="Comment your score")
    stack(
        score,
        [
            ("HOW DID YOU DO?", 32, theme.highlight, 40),
            (f"{total} out of {total}?", 76, theme.text, 40),
            ("Which border surprised you?", 40, theme.text, 28),
            ("Tell us your score in the comments.", 32, theme.muted, 0),
        ],
    )
    post.add(score, kind="scorecard", alt=f"How many of the {total} questions did you get right?")
    post.finish()
    return post.paths
