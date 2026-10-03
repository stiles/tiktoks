"""Build the tables behind each slide and print the numbers the narration quotes."""

import json
from pathlib import Path

import pandas as pd

from tiktoks.io import read_yaml
from tiktoks.paths import ensure_dir, story_data

HERE = Path(__file__).resolve().parent
# A month needs this many days, and a year this many, before it counts.
MIN_MONTH_DAYS = 25
MIN_YEAR_DAYS = 330


def load_daily(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    for column in ("hi", "lo"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["avg"] = (df["hi"] + df["lo"]) / 2
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    return df


def month_normals(df: pd.DataFrame, start: int, end: int) -> pd.DataFrame:
    base = df[df["year"].between(start, end)]
    table = base.groupby("month")[["hi", "lo", "avg"]].mean()
    table["rank_hi"] = table["hi"].rank(ascending=False, method="min").astype(int)
    return table.reset_index()


def hottest_day_months(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    full = df.groupby("year").filter(lambda year: year["hi"].count() >= MIN_YEAR_DAYS)
    months = full.loc[full.groupby("year")["hi"].idxmax(), "month"]
    share = months.value_counts(normalize=True).reindex(range(1, 13), fill_value=0.0)
    return share.rename_axis("month").reset_index(name="share"), len(months)


def septembers(df: pd.DataFrame, start: int, end: int, threshold: int) -> pd.DataFrame:
    sep = df[df["month"] == 9]
    table = sep.groupby("year").agg(
        days=("hi", "count"),
        avg=("avg", "mean"),
        hi=("hi", "mean"),
        lo=("lo", "mean"),
        warm_nights=("lo", lambda lows: int((lows >= threshold).sum())),
    )
    table = table[table["days"] >= MIN_MONTH_DAYS]
    table["departure"] = table["avg"] - table.loc[start:end, "avg"].mean()
    table["rank"] = table["avg"].rank(ascending=False, method="min").astype(int)
    return table.reset_index()


def main() -> None:
    config = read_yaml(HERE / "story.yaml")
    root = story_data(config["slug"])
    raw, out = root / "raw", ensure_dir(root / "processed")
    start, end = config["normals"]
    year = config["year"]
    downtown = config["stations"]["downtown"]["sid"]
    lax = config["stations"]["lax"]["sid"]

    daily = {sid: load_daily(raw / f"daily_{sid}.csv") for sid in (downtown, lax)}
    month_normals(daily[downtown], start, end).to_csv(out / "month_normals.csv", index=False)

    counts = {}
    for key, station in config["stations"].items():
        share, years = hottest_day_months(daily[station["sid"]])
        share.to_csv(out / f"hottest_month_{key}.csv", index=False)
        counts[key] = years

    sep = septembers(daily[lax], start, end, config["warm_night"])
    sep.to_csv(out / "septembers_lax.csv", index=False)

    normals = pd.read_csv(raw / f"normals_{lax}.csv", parse_dates=["date"])
    summer = daily[lax][daily[lax]["date"] >= f"{year}-07-01"].merge(normals, on="date")
    summer = summer.dropna(subset=["hi", "lo"])
    summer[["date", "hi", "lo", "normal_hi", "normal_lo"]].to_csv(
        out / "summer_lax.csv", index=False
    )

    this_sep = sep.set_index("year").loc[year]
    base_nights = sep.set_index("year").loc[start:end, "warm_nights"].mean()
    in_sep = summer[summer["date"].dt.month == 9]
    peak = summer.loc[summer["hi"].idxmax()]
    facts = {
        "through": summer["date"].max().strftime("%Y-%m-%d"),
        "hottest_day_years": counts,
        "september_rank": int(this_sep["rank"]),
        "september_years": len(sep),
        "september_first_year": int(sep["year"].min()),
        "september_departure": round(float(this_sep["departure"]), 2),
        "september_days_above_normal_high": int((in_sep["hi"] > in_sep["normal_hi"]).sum()),
        "september_days": len(in_sep),
        "warm_nights": int(this_sep["warm_nights"]),
        "warm_nights_normal": round(float(base_nights), 1),
        "peak_high": int(peak["hi"]),
        "peak_date": peak["date"].strftime("%Y-%m-%d"),
    }
    (out / "facts.json").write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")
    for key, value in facts.items():
        print(f"{key:36} {value}")


if __name__ == "__main__":
    main()
