"""The country pool and the batches built from it."""

from pathlib import Path

import pandas as pd
import pytest

from tiktoks import batches, countries
from tiktoks.maps import needs_locator, prepare_country, world_countries


@pytest.fixture
def pool(tmp_path) -> Path:
    frame = pd.DataFrame(
        [
            {"name": "Alpha", "tier": "easy", "times_used": 0, "last_rendered": ""},
            {"name": "Bravo", "tier": "easy", "times_used": 0, "last_rendered": ""},
            {"name": "Charlie", "tier": "easy", "times_used": 2, "last_rendered": "2026-01-01"},
            {"name": "Delta", "tier": "easy", "times_used": 1, "last_rendered": "2026-06-01"},
            {"name": "Echo", "tier": "expert", "times_used": 0, "last_rendered": ""},
        ]
    )
    for column in countries.COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    path = tmp_path / "countries.csv"
    frame[countries.COLUMNS].to_csv(path, index=False)
    return path


def test_selection_prefers_unused_then_least_recent(pool):
    frame = countries.load(pool)
    chosen = list(countries.select(frame, "easy", 4)["name"])
    assert chosen[:2] == ["Alpha", "Bravo"]
    # Charlie last ran in January, Delta in June, so Charlie is staler.
    assert chosen[2:] == ["Charlie", "Delta"]


def test_selection_refuses_to_overdraw_a_tier(pool):
    frame = countries.load(pool)
    with pytest.raises(ValueError, match="the pool has 1"):
        countries.select(frame, "expert", 3)


def test_selection_rejects_an_unknown_tier(pool):
    with pytest.raises(ValueError, match="Unknown tier"):
        countries.select(countries.load(pool), "impossible", 1)


def test_marking_rendered_advances_the_next_pick(pool):
    frame = countries.load(pool)
    first = list(countries.select(frame, "easy", 2)["name"])
    countries.save(countries.mark_rendered(frame, first), pool)

    second = list(countries.select(countries.load(pool), "easy", 2)["name"])
    assert set(first) & set(second) == set()


def test_batch_writes_a_config_and_records_usage(pool, tmp_path):
    root = tmp_path / "quizzes"
    path, names = batches.build("easy", 2, root=root, catalog_path=pool)
    assert path.exists()
    assert names == ["Alpha", "Bravo"]
    assert countries.load(pool).set_index("name").loc["Alpha", "times_used"] == 1


def test_dry_run_changes_nothing(pool, tmp_path):
    path, names = batches.build("easy", 2, root=tmp_path, catalog_path=pool, commit=False)
    assert not path.exists()
    assert countries.load(pool)["times_used"].sum() == 3  # unchanged fixture total


def test_batch_slugs_do_not_collide(pool, tmp_path):
    root = tmp_path / "quizzes"
    first, _ = batches.build("easy", 1, root=root, catalog_path=pool)
    second, _ = batches.build("easy", 1, root=root, catalog_path=pool)
    assert first != second
    assert first.parent.name == "geo-easy-001"
    assert second.parent.name == "geo-easy-002"


def test_entries_drop_blank_overrides(pool):
    frame = countries.load(pool)
    entry = countries.to_entries(frame.head(1))[0]
    assert set(entry) == {"name", "fact"}


def test_entries_carry_overrides_that_are_set():
    frame = pd.DataFrame(
        [
            {column: "" for column in countries.COLUMNS}
            | {"name": "X", "zoom": "2.5", "context": "world"}
        ]
    )
    entry = countries.to_entries(frame)[0]
    assert entry["zoom"] == 2.5
    assert entry["context"] == "world"


def test_shipped_pool_names_all_resolve():
    """Every name in the real catalog must match exactly one polygon."""
    assert countries.validate(countries.load()) == []


def test_tiny_island_nations_get_a_locator_ring():
    """Comoros is specks at any zoom that also shows a reference coastline."""
    world = world_countries()
    assert needs_locator(prepare_country(world, ["Comoros"], zoom=4.5))
    assert needs_locator(prepare_country(world, ["Sao Tome and Principe"], zoom=3.0))


def test_ordinary_countries_do_not_get_a_ring():
    world = world_countries()
    for name in ("The Gambia", "Lesotho", "Brunei", "Italy"):
        assert not needs_locator(prepare_country(world, [name]))


def test_a_rendered_batch_opens_on_a_cover(tmp_path):
    """A quiz starts on a cover that states the stakes, not on the first map."""
    import json

    from tiktoks.geo_quiz import render_geo_quiz
    from tiktoks.io import write_yaml

    config = tmp_path / "quiz.yaml"
    write_yaml(
        config,
        {
            "slug": "cover-test",
            "difficulty": "easy",
            "output_dir": "output",
            "countries": [{"name": "Italy", "fact": "A boot."}],
        },
    )
    render_geo_quiz(config)

    manifest = json.loads((tmp_path / "output" / "night" / "post.json").read_text())
    kinds = [slide["kind"] for slide in manifest["slides"]]
    assert kinds == ["cover", "prompt", "answer", "scorecard"]
    assert manifest["layout_problems"] == []
