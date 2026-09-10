import pandas as pd

from tiktoks.ssa_names import rank_trends, share_by_year, top_names_by_sex
from tiktoks.ssa_story import _series_point


def test_rank_trends_filters_and_orders() -> None:
    names = pd.DataFrame(
        {
            "name": ["Ava", "Ava", "Lainey", "Lainey", "Mabel", "Mabel"],
            "sex": ["F", "F", "F", "F", "F", "F"],
            "births": [10_000, 7_000, 100, 4_000, 50, 60],
            "year": [2020, 2025, 2020, 2025, 2020, 2025],
        }
    )
    shares = share_by_year(names)
    totals = shares.groupby("year")["births_all"].first()
    assert totals[2020] == 10_150
    assert totals[2025] == 11_060

    rising, falling = rank_trends(
        names,
        start_year=2020,
        end_year=2025,
        rising_min_births=3_000,
        falling_min_births=8_000,
        top_n=5,
    )
    assert rising.iloc[0]["name"] == "Lainey"
    assert falling.iloc[0]["name"] == "Ava"
    assert rising.iloc[0]["share_change"] > 0
    assert falling.iloc[0]["share_change"] < 0


def test_top_names_by_sex() -> None:
    names = pd.DataFrame(
        {
            "state": ["TX"] * 8,
            "sex": ["F", "F", "F", "F", "M", "M", "M", "M"],
            "year": [2025, 2025, 2025, 2025, 2025, 2025, 2025, 2025],
            "name": ["Olivia", "Emma", "Ava", "Mia", "Liam", "Noah", "Oliver", "Elijah"],
            "births": [2000, 1800, 1600, 1400, 2200, 2100, 1900, 1700],
        }
    )
    girls, boys = top_names_by_sex(names, 2025, top_n=3)
    assert list(girls["name"]) == ["Olivia", "Emma", "Ava"]
    assert list(boys["name"]) == ["Liam", "Noah", "Oliver"]
    assert girls.iloc[0]["rank"] == 1


def test_series_point_returns_one_year_or_none() -> None:
    series = pd.DataFrame(
        {
            "year": [2010, 2020],
            "share_per_100k": [10.0, 5.0],
            "births": [100, 50],
        }
    )
    assert _series_point(series, 2020)["births"] == 50
    assert _series_point(series, 1999) is None
