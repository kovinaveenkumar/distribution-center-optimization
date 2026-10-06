"""Part 4 helpers - Tableau-ready CSVs + static charts for the README."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC, OUT, ASSETS = ROOT / "data" / "processed", ROOT / "data" / "outputs", ROOT / "assets"
ASSETS.mkdir(exist_ok=True)

SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e6e5e1"
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
REGION_COLOR = {"West": BLUE, "South": ORANGE, "Midwest": AQUA}
DC_COLOR = {"DC1": BLUE, "DC2": ORANGE, "DC3": AQUA, "DC4": YELLOW}

plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
                     "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": MUTED,
                     "ytick.color": MUTED, "text.color": INK, "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8})


def k(x, _=None):
    return f"{x/1000:,.0f}k"


def tableau_tables():
    reg = pd.read_csv(PROC / "regional_weekly_volume.csv", parse_dates=["week_start"])
    bt = pd.read_csv(PROC / "backtest_predictions.csv", parse_dates=["week_start"])
    fc = pd.read_csv(PROC / "forecast_next_12_weeks.csv", parse_dates=["week_start"])
    acc = pd.read_csv(PROC / "forecast_accuracy.csv")
    best = fc.groupby("region").model.first()
    bt = bt[bt.model == bt.region.map(best)]
    a = reg.assign(series="Actual", model="", lower_80=np.nan, upper_80=np.nan).rename(columns={"units": "units"})
    b = bt.rename(columns={"forecast": "units"}).assign(series="Backtest forecast")[
        ["region", "week_start", "units", "series", "model"]].assign(lower_80=np.nan, upper_80=np.nan)
    f = fc.rename(columns={"forecast": "units"}).assign(series="Forecast")
    cols = ["region", "week_start", "series", "model", "units", "lower_80", "upper_80"]
    demand = pd.concat([a[cols], b[cols], f[cols]]).sort_values(["region", "week_start", "series"])
    demand.to_csv(OUT / "tableau_demand_forecast.csv", index=False)
    acc.to_csv(OUT / "tableau_forecast_accuracy.csv", index=False)
    return reg, bt, fc, acc


def chart_forecast(reg, bt, fc):
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    for ax, region in zip(axes, ["West", "Midwest", "South"]):
        c = REGION_COLOR[region]
        r = reg[(reg.region == region) & (reg.week_start >= "2014-06-01")]
        b = bt[bt.region == region]
        f = fc[fc.region == region]
        ax.plot(r.week_start, r.units, color=c, lw=2)
        ax.plot(b.week_start, b.forecast, color=INK2, lw=1.6, ls=(0, (4, 3)))
        ax.fill_between(f.week_start, f.lower_80, f.upper_80, color=c, alpha=0.18, lw=0)
        ax.plot(f.week_start, f.forecast, color=c, lw=2, ls=(0, (1, 1.5)))
        ax.axvline(reg.week_start.max(), color=MUTED, lw=1)
        ax.set_title(f"{region}  ·  {f.model.iloc[0]}", loc="left", fontsize=11, color=INK)
        ax.yaxis.set_major_formatter(k)
        ax.set_ylabel("units / week")
        if region == "West":
            ax.text(r.week_start.iloc[8], r.units.max() * 0.98, "actual", color=c, fontsize=9, va="top")
            ax.text(b.week_start.iloc[6], b.forecast.min() * 0.9, "backtest (out-of-sample)", color=INK2, fontsize=9)
            ax.text(f.week_start.iloc[0], f.lower_80.min() * 0.93, "next 12 wks\n(80% band)", color=c, fontsize=9, va="top")
    fig.suptitle("Weekly demand: actual, out-of-sample backtest, and 12-week forecast", x=0.01, ha="left", fontsize=13)
    fig.tight_layout()
    fig.savefig(ASSETS / "04_forecast_vs_actual.png", dpi=140)
    plt.close(fig)


def chart_accuracy(acc):
    p = acc.pivot(index="region", columns="model", values="MAPE_%").loc[["West", "Midwest", "South"]]
    order = ["Seasonal naive", "ARIMA+Fourier", "Prophet"]
    cols = [MUTED, ORANGE, BLUE]
    fig, ax = plt.subplots(figsize=(8, 4))
    w = 0.26
    for i, (m, c) in enumerate(zip(order, cols)):
        xs = np.arange(len(p)) + (i - 1) * (w + 0.02)
        ax.bar(xs, p[m], w, color=c, label=m)
        for x, v in zip(xs, p[m]):
            ax.text(x, v + 0.2, f"{v:.1f}", ha="center", fontsize=8.5, color=INK2)
    ax.set_xticks(range(len(p)), p.index)
    ax.set_ylabel("MAPE % (48 weeks, 4 rolling folds)")
    ax.set_title("Forecast error by model (lower is better)", loc="left", fontsize=12)
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, ncol=3, loc="upper left", bbox_to_anchor=(0, -0.1))
    fig.tight_layout()
    fig.savefig(ASSETS / "05_model_mape.png", dpi=140)
    plt.close(fig)


def chart_scenarios(summ, util):
    s = summ[summ.demand_case == "base"].copy()
    s["label"] = ["As-is", "Optimized", "+30k at\nPhoenix (DC1)", "+30k at\nDallas (DC2)"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), gridspec_kw={"width_ratios": [1, 1.25]})
    ax = axes[0]
    cols = [MUTED, BLUE, BLUE, BLUE]
    op = (s.ship + s.hand + s.over_cost).values / 1e6
    ex = s.expansion.values / 1e6
    ax.bar(s.label, op, color=cols, edgecolor=SURF, linewidth=2, width=0.6)
    ax.bar(s.label, ex, bottom=op, color=SURF, edgecolor=BLUE, hatch="///", linewidth=1.2, width=0.6)
    for x, tot, sv in zip(range(len(s)), s.total / 1e6, s.savings_vs_asis):
        txt = f"${tot:.2f}M" + ("" if x == 0 else f"\n{'−' if sv > 0 else '+'}${abs(sv)/1e3:,.0f}k vs as-is")
        ax.text(x, tot + 0.04, txt, ha="center", fontsize=9, color=INK)
    ax.set_ylim(0, s.total.max() / 1e6 * 1.2)
    ax.set_ylabel("12-week network cost ($M)")
    ax.set_title("12-wk cost (hatched = assumed expansion charge)", loc="left", fontsize=11)
    ax.grid(axis="x", visible=False)
    ax2 = axes[1]
    u = util[(util.demand_case == "base")].groupby(["scenario", "dc"]).utilization.mean().unstack()
    u = u.loc[sorted(u.index)]
    xs = np.arange(len(u)); w = 0.2
    for i, dc in enumerate(["DC1", "DC2", "DC3", "DC4"]):
        ax2.bar(xs + (i - 1.5) * (w + 0.015), u[dc] * 100, w, color=DC_COLOR[dc], label=dc)
    ax2.axhline(100, color=INK2, lw=1, ls="--")
    ax2.text(len(u) - 0.5, 101.5, "capacity", ha="right", fontsize=8.5, color=INK2)
    ax2.set_xticks(xs, s.label)
    ax2.set_ylim(0, 112)
    ax2.set_ylabel("average weekly utilization %")
    ax2.set_title("How full each DC runs", loc="left", fontsize=11)
    ax2.legend(frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.17))
    ax2.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(ASSETS / "06_scenarios_cost_utilization.png", dpi=140)
    plt.close(fig)


def chart_flows(assign):
    a = assign[(assign.demand_case == "base")
               & assign.scenario.str.startswith(("0", "1", "2"))]
    a = a.groupby(["scenario", "region", "dc"]).units.sum().reset_index()
    names = sorted(a.scenario.unique())
    titles = ["As-is", "Optimized", "Optimized + Phoenix"]
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharey=True)
    for ax, sc, t in zip(axes, names, titles):
        d = a[a.scenario == sc].pivot(index="region", columns="dc", values="units").fillna(0)
        d = d.loc[["West", "Midwest", "South"]]
        left = np.zeros(len(d))
        for dc in [c for c in ["DC1", "DC2", "DC3", "DC4"] if c in d]:
            ax.barh(d.index, d[dc] / 1e6, left=left, color=DC_COLOR[dc], edgecolor=SURF, linewidth=2, label=dc)
            left += d[dc].values / 1e6
        ax.set_title(t, loc="left", fontsize=11)
        ax.invert_yaxis(); ax.grid(axis="y", visible=False)
        ax.set_xlabel("12-wk units (M)")
    axes[0].legend(frameon=False, ncol=4, loc="upper left", bbox_to_anchor=(0, -0.2), title="serving DC", alignment="left")
    fig.suptitle("Which DC serves each region (base forecast, 12 weeks)", x=0.01, ha="left", fontsize=12)
    fig.tight_layout()
    fig.savefig(ASSETS / "07_flows_by_scenario.png", dpi=140)
    plt.close(fig)


def main():
    reg, bt, fc, acc = tableau_tables()
    chart_forecast(reg, bt, fc)
    chart_accuracy(acc)
    summ = pd.read_csv(OUT / "scenario_summary.csv")
    util = pd.read_csv(OUT / "dc_utilization.csv")
    assign = pd.read_csv(OUT / "assignments.csv")
    chart_scenarios(summ, util)
    chart_flows(assign)
    # one wide table for the Tableau dashboard
    util.merge(pd.read_csv(ROOT / "data" / "dc_network.csv")[["dc", "city", "lat", "lon"]], on="dc") \
        .to_csv(OUT / "tableau_dc_utilization.csv", index=False)
    summ.to_csv(OUT / "tableau_scenario_summary.csv", index=False)
    assign.merge(pd.read_csv(ROOT / "data" / "regions.csv")[["region", "lat", "lon"]]
                 .rename(columns={"lat": "region_lat", "lon": "region_lon"}), on="region") \
        .to_csv(OUT / "tableau_assignments.csv", index=False)
    print(sorted(p.name for p in OUT.iterdir()), sorted(p.name for p in ASSETS.iterdir()))


if __name__ == "__main__":
    main()
