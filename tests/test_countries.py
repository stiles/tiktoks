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


def test_selection_can_draw_from_the_whole_pool(pool):
    frame = countries.load(pool)
    chosen = list(countries.select(frame, None, 3, by_tier=False)["name"])
    assert chosen == ["Alpha", "Bravo", "Echo"]


def test_marking_rendered_advances_the_next_pick(pool):
    frame = countries.load(pool)
    first = list(countries.select(frame, "easy", 2)["name"])
    countries.save(countries.mark_rendered(frame, first), pool)

    second = list(countries.select(countries.load(pool), "easy", 2)["name"])
    assert set(first) & set(second) == set()


def test_same_day_batches_rotate_before_repeating_low_usage_countries(pool):
    from datetime import UTC, datetime

    frame = countries.load(pool)
    frame["last_rendered"] = "2026-09-20"
    frame["times_used"] = [1, 1, 20, 20, 1]
    picks = []
    for hour in (10, 11):
        names = list(countries.select(frame, "easy", 2)["name"])
        picks.extend(names)
        countries.save(
            countries.mark_rendered(frame, names, datetime(2026, 9, 20, hour, tzinfo=UTC)), pool
        )
        frame = countries.load(pool)
    assert picks == ["Alpha", "Bravo", "Charlie", "Delta"]
    assert list(countries.select(frame, "easy", 2)["name"]) == ["Alpha", "Bravo"]


def test_default_usage_stamp_includes_time(pool):
    from datetime import datetime

    frame = countries.mark_rendered(countries.load(pool), ["Alpha"])
    stamp = frame.set_index("name").loc["Alpha", "last_rendered"]
    assert "T" in stamp
    assert datetime.fromisoformat(stamp).tzinfo is not None


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


def test_master_shares_expert_pool_and_records_usage(pool, tmp_path):
    from tiktoks.io import read_yaml

    path, names = batches.build("master", 1, root=tmp_path, catalog_path=pool)
    assert names == ["Echo"]
    assert path.parent.name == "geo-master-001"
    assert read_yaml(path)["difficulty"] == "master"
    frame = countries.load(pool)
    assert frame.set_index("name").loc["Echo", "times_used"] == 1
    status = countries.status(frame).set_index("tier")
    assert status.loc["master", "total"] == status.loc["expert", "total"] == 1


def test_master_rejects_other_variants_before_writing(pool, tmp_path):
    with pytest.raises(ValueError, match="isolated outlines"):
        batches.build("master", 1, root=tmp_path, catalog_path=pool, variant="silhouette")
    assert not (tmp_path / "geo-silhouette-master-001").exists()


def test_batch_slugs_do_not_collide(pool, tmp_path):
    root = tmp_path / "quizzes"
    first, _ = batches.build("easy", 1, root=root, catalog_path=pool)
    second, _ = batches.build("easy", 1, root=root, catalog_path=pool)
    assert first != second
    assert first.parent.name == "geo-easy-001"
    assert second.parent.name == "geo-easy-002"


def test_silhouette_batches_use_global_selection_and_own_slug(pool, tmp_path):
    root = tmp_path / "quizzes"
    path, names = batches.build("expert", 2, root=root, catalog_path=pool, variant="silhouette")
    assert names == ["Alpha", "Bravo"]
    assert path.parent.name == "geo-silhouette-expert-001"
    config = path.read_text()
    assert "variant: silhouette" in config


def test_progressive_batches_use_global_selection_and_own_slug(pool, tmp_path):
    root = tmp_path / "quizzes"
    path, names = batches.build("hard", 2, root=root, catalog_path=pool, variant="progressive")
    assert names == ["Alpha", "Bravo"]
    assert path.parent.name == "geo-progressive-hard-001"
    config = path.read_text()
    assert "variant: progressive" in config


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
    assert needs_locator(prepare_country(world, ["Maldives"], zoom=6))
    assert needs_locator(prepare_country(world, ["Palau"], zoom=14))
    # A landlocked sliver needs one too, not just an island.
    assert needs_locator(prepare_country(world, ["Liechtenstein"]))


def test_ordinary_countries_do_not_get_a_ring():
    world = world_countries()
    for name in ("The Gambia", "Lesotho", "Brunei", "Italy", "Malta", "Andorra"):
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
            "countries": [{"name": "Italy", "fact": "A boot."}],
        },
    )
    render_geo_quiz(config)

    manifest = json.loads((tmp_path / "night" / "post.json").read_text())
    kinds = [slide["kind"] for slide in manifest["slides"]]
    assert kinds == ["cover", "prompt", "answer", "scorecard"]
    assert manifest["layout_problems"] == []


def test_silhouette_batch_uses_variant_defaults(tmp_path):
    """Silhouette quizzes change the cover copy and stay layout-safe."""
    import json

    from tiktoks.geo_quiz import render_geo_quiz
    from tiktoks.io import write_yaml

    config = tmp_path / "quiz.yaml"
    write_yaml(
        config,
        {
            "slug": "silhouette-test",
            "variant": "silhouette",
            "difficulty": "easy",
            "countries": [{"name": "Italy", "fact": "A boot."}],
        },
    )
    render_geo_quiz(config)

    manifest = json.loads((tmp_path / "night" / "post.json").read_text())
    assert manifest["topic"] == "world geography silhouettes"
    assert manifest["layout_problems"] == []


def test_progressive_batch_inserts_a_hint_slide(tmp_path):
    """Progressive quizzes go prompt, hint, answer for each country."""
    import json

    from tiktoks.geo_quiz import render_geo_quiz
    from tiktoks.io import write_yaml

    config = tmp_path / "quiz.yaml"
    write_yaml(
        config,
        {
            "slug": "progressive-test",
            "variant": "progressive",
            "difficulty": "medium",
            "countries": [{"name": "Italy", "fact": "A boot."}],
        },
    )
    render_geo_quiz(config)

    manifest = json.loads((tmp_path / "night" / "post.json").read_text())
    kinds = [slide["kind"] for slide in manifest["slides"]]
    assert kinds == ["cover", "prompt", "hint", "answer", "scorecard"]
    assert manifest["topic"] == "world geography progressive reveals"
    assert manifest["layout_problems"] == []


def test_master_prompts_are_isolated_and_answers_restore_context(tmp_path, monkeypatch):
    import json

    from tiktoks import geo_quiz
    from tiktoks.io import write_yaml

    draws = []
    outline = geo_quiz.draw_outline
    highlight = geo_quiz.draw_highlight

    def record_outline(ax, view, **kwargs):
        draws.append(("outline", len(view.base)))
        outline(ax, view, **kwargs)

    def record_highlight(ax, view, **kwargs):
        draws.append(("regional", len(view.base)))
        highlight(ax, view, **kwargs)

    monkeypatch.setattr(geo_quiz, "draw_outline", record_outline)
    monkeypatch.setattr(geo_quiz, "draw_highlight", record_highlight)
    config = tmp_path / "quiz.yaml"
    write_yaml(
        config,
        {
            "slug": "master-test",
            "difficulty": "master",
            "countries": [{"name": "Eswatini", "match_name": "Swaziland", "fact": "Test fact."}],
        },
    )
    geo_quiz.render_geo_quiz(config)
    assert draws[0] == ("outline", 1)
    assert draws[1][0] == "regional" and draws[1][1] > 1
    manifest = json.loads((tmp_path / "night" / "post.json").read_text())
    assert [s["kind"] for s in manifest["slides"]] == ["cover", "prompt", "answer", "scorecard"]
    assert manifest["slides"][1]["title"] is None  # no answer in prompt metadata
    assert manifest["topic"] == "world geography outlines"
    assert manifest["layout_problems"] == []
