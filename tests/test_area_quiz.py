import json
from pathlib import Path

import numpy as np
import pytest

from tiktoks.area_quiz import comparison_views, render_area_quiz, winner_index
from tiktoks.io import read_yaml, write_yaml
from tiktoks.maps import prepare_outline, quiz_countries

PILOT = Path("content/area-quiz/area-001/quiz.yaml")


def test_pilot_values_match_saved_world_bank_response():
    config = read_yaml(PILOT)
    payload = json.loads(PILOT.with_name("source.json").read_text())
    rows = {row["countryiso3code"]: row for row in payload[1]}
    for question in config["questions"]:
        winner_index(question["choices"])
        for choice in question["choices"]:
            row = rows[choice["iso3"]]
            assert choice["land_km2"] == row["value"]
            assert int(row["date"]) == config["year"]
            assert row["indicator"]["id"] == config["indicator"]


@pytest.mark.parametrize("values", [(10, 10), (-1, 10), (float("nan"), 10), (10,)])
def test_rejects_invalid_comparisons(values):
    with pytest.raises(ValueError):
        winner_index([{"land_km2": v} for v in values])


def test_answer_maps_share_bounds_without_rescaling_geometry():
    world = quiz_countries()
    choices = [{"name": "Japan"}, {"name": "Italy"}]
    views = comparison_views(world, choices)
    assert views[0].bounds == views[1].bounds
    for choice, view in zip(choices, views, strict=True):
        original = prepare_outline(world, choice["name"]).target
        assert np.isclose(original.area.sum(), view.target.area.sum())
        x0, y0, x1, y1 = view.target.total_bounds
        left, bottom, right, top = view.bounds
        assert left < x0 < x1 < right and bottom < y0 < y1 < top


def test_area_quiz_render_and_manifest(tmp_path):
    config = read_yaml(PILOT)
    config["questions"] = config["questions"][:1]
    path = tmp_path / "quiz.yaml"
    write_yaml(path, config)
    output = tmp_path / "render"
    render_area_quiz(path, "paper", output_dir=output)
    manifest = json.loads((output / "post.json").read_text())
    assert [s["kind"] for s in manifest["slides"]] == ["cover", "prompt", "answer", "scorecard"]
    assert manifest["slides"][1]["title"] is None
    assert manifest["slides"][2]["title"] == "Japan"
    assert manifest["layout_problems"] == []
    assert manifest["format"] == "area-quiz"
