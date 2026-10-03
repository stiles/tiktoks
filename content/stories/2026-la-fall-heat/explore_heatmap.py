"""Exploration, not part of the post: LAX monthly mean-temperature heatmap since
1936 and 2026 daily highs and lows against normals.

Run: uv run python content/stories/2026-la-fall-heat/explore_heatmap.py
Writes to data/stories/2026-la-fall-heat/explore/.
"""

from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests

from tiktoks.paths import story_data

SID = "045114"  # LOS ANGELES INTL AP
YEAR = 2026
OUT = story_data(Path(__file__).resolve().parent.name) / "explore"
OUT.mkdir(parents=True, exist_ok=True)


def acis(params: dict) -> list:
    r = requests.post("https://data.rcc-acis.org/StnData", json={"sid": SID, **params}, timeout=60)
    r.raise_for_status()
    return r.json()["data"]


def to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.replace({"M": np.nan, "T": np.nan}), errors="coerce")


# Monthly mean of daily avg temp, same 5-missing-day rule as the WRCC table
monthly = pd.DataFrame(
    acis(
        {
            "sdate": "por",
            "edate": "por",
            "elems": [
                {
                    "name": "avgt",
                    "interval": "mly",
                    "duration": "mly",
                    "reduce": "mean",
                    "maxmissing": 5,
                }
            ],
        }
    ),
    columns=["ym", "avgt"],
)
monthly["avgt"] = to_num(monthly["avgt"])
monthly["year"] = monthly["ym"].str[:4].astype(int)
monthly["month"] = monthly["ym"].str[5:].astype(int)
grid = monthly.pivot(index="month", columns="year", values="avgt")
grid.to_csv(OUT / "lax_monthly_avgt.csv")

base = grid.loc[:, 1991:2020].mean(axis=1)
anom = grid.sub(base, axis=0)

months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
years = grid.columns.values

fig, axes = plt.subplots(2, 1, figsize=(16, 8), constrained_layout=True)
for ax, data, cmap, norm, label in [
    (axes[0], grid, "RdYlBu_r", None, "Monthly mean temperature (°F)"),
    (
        axes[1],
        anom,
        "RdBu_r",
        mcolors.TwoSlopeNorm(0, -6, 6),
        "Departure from 1991–2020 monthly mean (°F)",
    ),
]:
    m = ax.pcolormesh(
        np.append(years, years[-1] + 1) - 0.5,
        np.arange(0.5, 13.5),
        data.values,
        cmap=cmap,
        norm=norm,
        edgecolors="white",
        linewidth=0.3,
    )
    ax.set_yticks(range(1, 13), months)
    ax.invert_yaxis()
    ax.set_title(label, loc="left", fontsize=11)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.colorbar(m, ax=ax, shrink=0.8, pad=0.01)
fig.suptitle("Los Angeles International Airport, 1936–2026", x=0.01, ha="left", fontweight="bold")
fig.savefig(OUT / "lax_heatmap.png", dpi=150)

# Daily highs/lows this year vs. 1991–2020 daily normals
daily = pd.DataFrame(
    acis(
        {
            "sdate": f"{YEAR}-01-01",
            "edate": f"{YEAR}-12-31",
            "elems": [
                {"name": "maxt"},
                {"name": "mint"},
                {"name": "maxt", "normal": "1"},
                {"name": "mint", "normal": "1"},
            ],
        }
    ),
    columns=["date", "hi", "lo", "nhi", "nlo"],
)
daily["date"] = pd.to_datetime(daily["date"])
for c in ["hi", "lo", "nhi", "nlo"]:
    daily[c] = to_num(daily[c])
daily.to_csv(OUT / f"lax_daily_{YEAR}.csv", index=False)

# Each day's bar is stacked in 5-degree bands colored by temperature
bands = np.arange(30, 115, 5)
cmap = plt.get_cmap("Spectral_r")
cnorm = mcolors.Normalize(40, 100)

fig, ax = plt.subplots(figsize=(16, 5), constrained_layout=True)
obs = daily.dropna(subset=["hi", "lo"])
for lo_edge in bands:
    hi_edge = lo_edge + 5
    bottom = obs["lo"].clip(lo_edge, hi_edge)
    top = obs["hi"].clip(lo_edge, hi_edge)
    h = top - bottom
    keep = h > 0
    ax.bar(
        obs["date"][keep],
        h[keep],
        bottom=bottom[keep],
        width=1.0,
        color=cmap(cnorm(lo_edge + 2.5)),
        linewidth=0,
    )

ax.plot(daily["date"], daily["nhi"], color="#333", lw=1.4)
ax.plot(daily["date"], daily["nlo"], color="#333", lw=1.4)
last = daily.dropna(subset=["nhi"]).iloc[-1]
ax.text(last["date"], last["nhi"], "  Normal high", va="center", fontsize=9, fontweight="bold")
ax.text(last["date"], last["nlo"], "  Normal low", va="center", fontsize=9, fontweight="bold")

ax.xaxis.set_major_locator(mdates.MonthLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
ax.set_xlim(pd.Timestamp(f"{YEAR}-01-01"), pd.Timestamp(f"{YEAR}-12-31"))
ax.yaxis.tick_right()
ax.grid(axis="y", color="#ddd", lw=0.6)
ax.set_axisbelow(True)
for s in ["top", "left", "right"]:
    ax.spines[s].set_visible(False)
ax.set_title(
    f"LAX daily high and low, {YEAR}, vs. 1991–2020 normals (°F)", loc="left", fontweight="bold"
)
fig.savefig(OUT / f"lax_daily_{YEAR}.png", dpi=150)

print(f"Wrote {OUT}")
print(f"Months with data: {grid.notna().sum().sum()} / {grid.size}")
print(f"{YEAR} days above normal high: {(obs['hi'] > obs['nhi']).sum()} / {len(obs)}")
