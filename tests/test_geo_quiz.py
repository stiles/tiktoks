"""Progressive hints must reveal more geography at every country size."""

import matplotlib.pyplot as plt
import pytest

from tiktoks.geo_quiz import VARIANTS, _progressive_views
from tiktoks.maps import frame_axes, world_countries


@pytest.mark.parametrize("name", ["Oman", "Belize", "Japan", "Fiji", "Canada", "Zimbabwe"])
@pytest.mark.parametrize("detailed", [False, True])
def test_globe_clips_horizon_without_invalid_coordinates(name, detailed):
    import numpy as np
    from shapely import get_coordinates

    from tiktoks.maps import GLOBE_RADIUS, prepare_globe, quiz_countries

    view = prepare_globe(quiz_countries() if detailed else world_countries(), name)
    assert not view.target.empty
    assert view.target.area.sum() > 0
    for frame in (view.base, view.target):
        coords = get_coordinates(frame.geometry)
        assert np.isfinite(coords).all()
        assert np.linalg.norm(coords, axis=1).max() <= GLOBE_RADIUS * 1.00001
        assert frame.is_valid.all()


def test_globe_batch_uses_tier_and_renders_matching_views(tmp_path, monkeypatch):
    import json

    from tiktoks import batches, countries, geo_quiz
    from tiktoks.io import read_yaml

    catalog = tmp_path / "countries.csv"
    countries.save(countries.load(), catalog)
    config, names = batches.build("hard", 1, variant="globe", root=tmp_path, catalog_path=catalog)
    pool = countries.load(catalog).set_index("name")
    assert all(pool.loc[name, "tier"] == "hard" for name in names)
    assert read_yaml(config)["topic"] == "world geography globe quiz"
    views = []
    original = geo_quiz.draw_globe

    def record(ax, view, **kwargs):
        views.append(view)
        original(ax, view, **kwargs)

    monkeypatch.setattr(geo_quiz, "draw_globe", record)
    geo_quiz.render_geo_quiz(config, "night")
    assert len(views) == 2 and views[0] is views[1]
    manifest = json.loads((config.parent / "night" / "post.json").read_text())
    assert [s["kind"] for s in manifest["slides"]] == ["cover", "prompt", "answer", "scorecard"]
    assert manifest["slides"][1]["title"] is None
    assert manifest["layout_problems"] == []


@pytest.mark.parametrize(
    "name", ["Iran", "Papua New Guinea", "Sweden", "Ukraine", "United Kingdom", "Lesotho"]
)
@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard", "expert"])
def test_progressive_hint_expands_the_visible_window(name, difficulty):
    spec = VARIANTS["progressive"]
    prompt, hint = _progressive_views({"name": name}, world_countries(), difficulty, spec)
    expected = (
        spec["reveal_frame_by_difficulty"][difficulty]
        / spec["prompt_frame_by_difficulty"][difficulty]
    )
    fig, ax = plt.subplots()
    try:
        windows = []
        for view in (prompt, hint):
            frame_axes(ax, view.bounds, aspect=1.1)
            windows.append((ax.get_xlim(), ax.get_ylim()))
        for before, after in zip(*windows, strict=True):
            assert (after[1] - after[0]) / (before[1] - before[0]) == pytest.approx(expected)
            assert after[0] < before[0] < before[1] < after[1]
    finally:
        plt.close(fig)


def test_progressive_world_override_still_allows_a_regional_zoom_out():
    prompt, hint = _progressive_views(
        {"name": "Iran", "context": "world", "zoom": 1.2, "center": [54, 32]},
        world_countries(),
        "hard",
        VARIANTS["progressive"],
    )
    assert prompt.base.crs == hint.base.crs
    assert "laea" in prompt.base.crs.to_string()
    assert hint.bounds[2] - hint.bounds[0] > prompt.bounds[2] - prompt.bounds[0]
