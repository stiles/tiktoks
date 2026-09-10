"""Load and rank SSA baby name trends."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

RANK_COLUMNS = [
    "name",
    "births_start",
    "births_end",
    "share_start",
    "share_end",
    "share_change",
]

STATE_COLUMNS = ["state", "sex", "year", "name", "births"]
TOP_NAME_COLUMNS = ["rank", "name", "sex", "births", "share_per_100k"]


def read_year_file(path: Path) -> pd.DataFrame:
    year = int(path.stem.replace("yob", ""))
    df = pd.read_csv(path, names=["name", "sex", "births"])
    df["year"] = year
    return df


def load_names(raw_dir: Path) -> pd.DataFrame:
    files = sorted(raw_dir.glob("yob*.txt"))
    if not files:
        raise FileNotFoundError(f"No SSA year files in {raw_dir}")
    return pd.concat((read_year_file(path) for path in files), ignore_index=True)


def combined_by_name(names: pd.DataFrame) -> pd.DataFrame:
    return names.groupby(["year", "name"], as_index=False)["births"].sum()


def share_by_year(names: pd.DataFrame) -> pd.DataFrame:
    yearly_totals = names.groupby("year", as_index=False)["births"].sum().rename(
        columns={"births": "births_all"}
    )
    combined = combined_by_name(names)
    shares = combined.merge(yearly_totals, on="year")
    shares["share_per_100k"] = shares["births"] / shares["births_all"] * 100_000
    return shares


def name_series(names: pd.DataFrame, target: str) -> pd.DataFrame:
    key = target.casefold()
    shares = share_by_year(names)
    selected = shares[shares["name"].str.casefold() == key].copy()
    if selected.empty:
        raise ValueError(f"No SSA records for {target!r}")
    return selected.sort_values("year").reset_index(drop=True)


def rank_trends(
    names: pd.DataFrame,
    *,
    start_year: int,
    end_year: int,
    rising_min_births: int,
    rising_min_births_start: int = 0,
    falling_min_births: int,
    top_n: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return the fastest-rising and fastest-falling popular names between two years."""
    shares = share_by_year(names)
    window = shares[shares["year"].isin([start_year, end_year])].copy()
    pivot = window.pivot_table(
        index="name",
        columns="year",
        values=["births", "share_per_100k"],
        aggfunc="sum",
    )
    pivot.columns = [f"{metric}_{year}" for metric, year in pivot.columns]
    pivot = pivot.reset_index()

    births_start = f"births_{start_year}"
    births_end = f"births_{end_year}"
    share_start = f"share_per_100k_{start_year}"
    share_end = f"share_per_100k_{end_year}"

    ranked = pivot.dropna(subset=[births_start, births_end, share_start, share_end]).copy()
    ranked["share_change"] = ranked[share_end] - ranked[share_start]

    rising = (
        ranked[
            (ranked[births_end] >= rising_min_births)
            & (ranked[births_start] >= rising_min_births_start)
        ]
        .sort_values("share_change", ascending=False)
        .head(top_n)
        .rename(
            columns={
                births_start: "births_start",
                births_end: "births_end",
                share_start: "share_start",
                share_end: "share_end",
            }
        )[RANK_COLUMNS]
        .reset_index(drop=True)
    )
    falling = (
        ranked[ranked[births_start] >= falling_min_births]
        .sort_values("share_change", ascending=True)
        .head(top_n)
        .rename(
            columns={
                births_start: "births_start",
                births_end: "births_end",
                share_start: "share_start",
                share_end: "share_end",
            }
        )[RANK_COLUMNS]
        .reset_index(drop=True)
    )
    return rising, falling


def read_state_file(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, names=STATE_COLUMNS)


def load_state_names(raw_dir: Path, state: str) -> pd.DataFrame:
    path = raw_dir / f"{state.upper()}.TXT"
    if not path.exists():
        raise FileNotFoundError(f"No SSA state file for {state!r} in {raw_dir}")
    return read_state_file(path)


def state_share_by_year(names: pd.DataFrame) -> pd.DataFrame:
    totals = names.groupby(["year", "sex"], as_index=False)["births"].sum().rename(
        columns={"births": "births_all"}
    )
    shares = names.merge(totals, on=["year", "sex"])
    shares["share_per_100k"] = shares["births"] / shares["births_all"] * 100_000
    return shares


def state_name_series(names: pd.DataFrame, target: str, sex: str) -> pd.DataFrame:
    key = target.casefold()
    shares = state_share_by_year(names)
    selected = shares[
        (shares["name"].str.casefold() == key) & (shares["sex"] == sex)
    ].copy()
    if selected.empty:
        raise ValueError(f"No SSA records for {target!r} ({sex})")
    return selected.sort_values("year").reset_index(drop=True)


def top_names(names: pd.DataFrame, year: int, sex: str, top_n: int = 5) -> pd.DataFrame:
    shares = state_share_by_year(names)
    year_data = shares[(shares["year"] == year) & (shares["sex"] == sex)].copy()
    top = (
        year_data.sort_values("births", ascending=False)
        .head(top_n)
        .assign(rank=lambda frame: range(1, len(frame) + 1))
    )
    return top[["rank", "name", "sex", "births", "share_per_100k"]].reset_index(drop=True)


def top_names_by_sex(
    names: pd.DataFrame,
    year: int,
    top_n: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return top_names(names, year, "F", top_n), top_names(names, year, "M", top_n)
