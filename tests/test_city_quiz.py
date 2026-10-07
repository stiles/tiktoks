"""City globe quiz: pool integrity, batch building and the rendered sequence."""

import json

import pytest

from tiktoks import batches, cities
from tiktoks.io import read_yaml


def test_pool_rows_are_located_tiered_and_unique():
    pool = cities.load()
    assert set(pool["tier"]) <= set(cities.TIERS)
    assert not pool["name"].duplicated().any()
    assert (pool["lon"] != "").all() and (pool["lat"] != "").all()
    for tier in cities.TIERS:
        assert (pool["tier"] == tier).sum() >= 3


def test_master_is_not_a_city_tier():
    with pytest.raises(ValueError, match="Unknown city tier"):
        cities.select(cities.load(), "master", 3)


@pytest.mark.parametrize(
    ("name", "lon", "lat", "country"),
    [
        ("Lahore", 74.35, 31.55, "Pakistan"),
        ("Ulaanbaatar", 106.92, 47.92, "Mongolia"),
        # On the water; Natural Earth's generalized coast puts it just offshore.
        ("Montevideo", -56.19, -34.91, "Uruguay"),
    ],
)
def test_containing_country(name, lon, lat, country):
    from tiktoks.maps import containing_country, quiz_countries

    assert containing_country(quiz_countries(), lon, lat).iloc[0]["name"] == country, name


def test_city_batch_records_usage_and_renders_scored_sequence(tmp_path):
    catalog = tmp_path / "cities.csv"
    cities.save(cities.load(), catalog)
    config, names = batches.build("hard", 2, variant="cities", root=tmp_path, catalog_path=catalog)
    assert config.parent.name == "geo-cities-hard-001"
    saved = read_yaml(config)
    assert saved["variant"] == "cities"
    assert [entry["name"] for entry in saved["cities"]] == names
    assert all({"country", "lon", "lat"} <= set(entry) for entry in saved["cities"])

    pool = cities.load(catalog).set_index("name")
    assert all(pool.loc[name, "tier"] == "hard" for name in names)
    assert all(pool.loc[name, "times_used"] == 1 for name in names)

    # Rendered through the geo-quiz entry point, as `make rebuild` does.
    from tiktoks.geo_quiz import render_geo_quiz

    render_geo_quiz(config, "night")
    manifest = json.loads((config.parent / "night" / "post.json").read_text())
    kinds = [slide["kind"] for slide in manifest["slides"]]
    assert kinds == ["cover", "prompt", "answer", "prompt", "answer", "scorecard"]
    assert manifest["slides"][1]["title"] is None
    first = saved["cities"][0]
    assert manifest["slides"][2]["title"] == f"{first['name']}, {first['country']}"
    assert "out of 6" in manifest["slides"][-1]["alt"]
    assert manifest["layout_problems"] == []
