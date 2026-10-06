"""Part 1 - load M5 daily item-level sales, aggregate to store-week and region-week.

Uses Walmart's own week id (wm_yr_wk, Saturday-Friday) so weeks never straddle
a year boundary. Writes CSVs to data/processed and a SQLite db for SQL queries.
"""
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, PROC = ROOT / "data" / "raw", ROOT / "data" / "processed"
PROC.mkdir(parents=True, exist_ok=True)

REGION = {"CA": "West", "TX": "South", "WI": "Midwest"}


def load():
    sales = pd.read_csv(RAW / "sales_train_evaluation.csv")
    cal = pd.read_csv(RAW / "calendar.csv", parse_dates=["date"])
    return sales, cal


def store_daily(sales, cal):
    day_cols = [c for c in sales.columns if c.startswith("d_")]
    daily = sales.groupby("store_id")[day_cols].sum().T
    daily.index.name = "d"
    daily = daily.reset_index().merge(
        cal[["d", "date", "wm_yr_wk", "event_name_1"]], on="d")
    return daily, day_cols


def main():
    sales, cal = load()
    print("sales", sales.shape, "calendar", cal.shape)
    daily, _ = store_daily(sales, cal)
    stores = sorted(sales.store_id.unique())

    # ---- data quality checks (reported in notebook 01) ----
    dq = {
        "item_store_series": len(sales),
        "days": daily.shape[0],
        "date_min": str(daily.date.min().date()),
        "date_max": str(daily.date.max().date()),
        "missing_values_in_sales": int(sales.isna().sum().sum()),
        "duplicate_ids": int(sales.id.duplicated().sum()),
        "negative_sales": int((sales.filter(like="d_") < 0).sum().sum()),
        "pct_zero_item_days": round(float((sales.filter(like="d_") == 0).mean().mean()) * 100, 1),
        "store_days_with_zero_total": int((daily[stores] == 0).sum().sum()),
        "calendar_gaps": int((cal.date.diff().dt.days.dropna() != 1).sum()),
    }
    pd.Series(dq).to_csv(PROC / "data_quality_summary.csv", header=["value"])
    print(dq)

    # ---- store-week ----
    long = daily.melt(id_vars=["d", "date", "wm_yr_wk", "event_name_1"],
                      value_vars=stores, var_name="store_id", value_name="units")
    wk = (long.groupby(["store_id", "wm_yr_wk"])
              .agg(week_start=("date", "min"), days=("date", "count"), units=("units", "sum"))
              .reset_index())
    wk = wk[wk.days == 7].drop(columns="days")          # drop partial first/last weeks
    wk["state"] = wk.store_id.str[:2]
    wk["region"] = wk.state.map(REGION)
    wk = wk.sort_values(["store_id", "week_start"]).reset_index(drop=True)

    reg = (wk.groupby(["region", "week_start"], as_index=False)["units"].sum()
             .sort_values(["region", "week_start"]).reset_index(drop=True))
    wk.to_csv(PROC / "store_weekly_volume.csv", index=False)
    reg.to_csv(PROC / "regional_weekly_volume.csv", index=False)

    # category mix per region-week (useful for SQL / dashboard)
    cat = sales.groupby(["cat_id", "state_id"])[[c for c in sales.columns if c.startswith("d_")]].sum()
    cat = cat.T.reset_index().rename(columns={"index": "d"})
    cat.columns = ["_".join(c).strip("_") if isinstance(c, tuple) else c for c in cat.columns]
    cat = cat.merge(cal[["d", "date", "wm_yr_wk"]], on="d")
    catl = cat.melt(id_vars=["d", "date", "wm_yr_wk"], var_name="k", value_name="units")
    catl[["cat_id", "state_id"]] = catl.k.str.rsplit("_", n=1, expand=True)
    catw = (catl.groupby(["cat_id", "state_id", "wm_yr_wk"])
                .agg(week_start=("date", "min"), days=("date", "count"), units=("units", "sum"))
                .reset_index())
    catw = catw[catw.days == 7].drop(columns="days")
    catw["region"] = catw.state_id.map(REGION)
    catw.to_csv(PROC / "category_weekly_volume.csv", index=False)

    # ---- SQLite for the SQL part ----
    db = PROC / "supply_chain.db"
    if db.exists():
        db.unlink()
    with sqlite3.connect(db) as con:
        wk.assign(week_start=wk.week_start.astype(str)).to_sql("store_weekly", con, index=False)
        reg.assign(week_start=reg.week_start.astype(str)).to_sql("region_weekly", con, index=False)
        catw.assign(week_start=catw.week_start.astype(str)).to_sql("category_weekly", con, index=False)
    print("weeks per region:", reg.groupby("region").size().to_dict())
    print(reg.groupby("region").units.describe().round(0))


if __name__ == "__main__":
    main()
