import json
from copy import deepcopy
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

from tiktoks.io import read_yaml, write_yaml
from tiktoks.maps import quiz_countries
from tiktoks.neighbors_quiz import regional_view, render_neighbors_quiz, validate_question

PILOT = Path("content/neighbors-quiz/neighbors-001/quiz.yaml")


@pytest.mark.parametrize(
    "change",
    [
        {"choices": ["Chile"]},
        {"choices": ["Chile", "Chile"]},
        {"answer": "C"},
        {"sources": []},
        {"explanation": ""},
    ],
)
def test_rejects_unusable_questions(change):
    question = deepcopy(read_yaml(PILOT)["questions"][0])
    question.update(change)
    with pytest.raises(ValueError):
        validate_question(question)


def test_all_pilot_map_labels_fit_their_regions():
    geography = quiz_countries()
    for q in read_yaml(PILOT)["questions"]:
        validate_question(q)
        view = regional_view(geography, q["map"])
        left, bottom, right, top = view.bounds
        for label in q["map"]["labels"]:
            point = gpd.GeoSeries([Point(label["lon"], label["lat"])], crs="EPSG:4326")
            p = point.to_crs(view.crs).iloc[0]
            assert left < p.x < right and bottom < p.y < top


def test_neighbors_render_preserves_sources_and_hides_answers(tmp_path):
    config = read_yaml(PILOT)
    config["questions"] = config["questions"][:1]
    path = tmp_path / "quiz.yaml"
    write_yaml(path, config)
    render_neighbors_quiz(path, "paper", output_dir=tmp_path / "slides")
    manifest = json.loads((tmp_path / "slides/post.json").read_text())
    assert [s["kind"] for s in manifest["slides"]] == ["cover", "prompt", "answer", "scorecard"]
    assert manifest["slides"][1]["title"] is None
    assert manifest["slides"][2]["title"] == "Lesotho"
    assert config["questions"][0]["sources"][0] in manifest["sources"]
    assert manifest["layout_problems"] == []
    assert manifest["format"] == "neighbors-quiz"
