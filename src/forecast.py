"""Part 2 - forecast the next 12 weeks of volume per region.

Models compared (rolling-origin backtest, 4 folds x 12 weeks):
  * Seasonal naive  - same week last year (baseline)
  * ARIMA(1,1,1) + Fourier(K=4) yearly seasonality (SARIMAX)
  * Prophet - trend + yearly seasonality
Metric: MAPE (also reports WAPE/bias). Winner per region is refit on all data.
"""
import logging
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from prophet import Prophet
from statsmodels.tsa.statespace.sarimax import SARIMAX

warnings.filterwarnings("ignore")
logging.getLogger("cmdstanpy").setLevel(logging.ERROR)
logging.getLogger("prophet").setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
H, FOLDS, K = 12, 4, 4


def fourier(dates, k=K):
    t = (pd.DatetimeIndex(dates) - pd.Timestamp("2000-01-01")).days.values / 365.25
    cols = {}
    for i in range(1, k + 1):
        cols[f"s{i}"] = np.sin(2 * np.pi * i * t)
        cols[f"c{i}"] = np.cos(2 * np.pi * i * t)
    return pd.DataFrame(cols)


def f_snaive(train, future_dates):
    s = train.set_index("week_start").units
    return np.array([s.get(d - pd.Timedelta(weeks=52), np.nan) for d in future_dates])


def f_arima(train, future_dates):
    y = np.log(train.units.values)
    m = SARIMAX(y, exog=fourier(train.week_start), order=(1, 1, 1), trend="n").fit(disp=False)
    return np.exp(m.forecast(len(future_dates), exog=fourier(future_dates)))


def f_prophet(train, future_dates):
    df = train.rename(columns={"week_start": "ds", "units": "y"})[["ds", "y"]]
    m = Prophet(yearly_seasonality=6, weekly_seasonality=False, daily_seasonality=False,
                seasonality_mode="multiplicative", changepoint_prior_scale=0.1)
    m.fit(df)
    return m.predict(pd.DataFrame({"ds": future_dates}))["yhat"].values


MODELS = {"Seasonal naive": f_snaive, "ARIMA+Fourier": f_arima, "Prophet": f_prophet}


def mape(a, f):
    return float(np.mean(np.abs((a - f) / a)) * 100)


def main():
    reg = pd.read_csv(PROC / "regional_weekly_volume.csv", parse_dates=["week_start"])
    bt_rows, metric_rows = [], []
    for region, g in reg.groupby("region"):
        g = g.sort_values("week_start").reset_index(drop=True)
        n = len(g)
        for fold in range(FOLDS):
            cut = n - H * (FOLDS - fold)
            train, test = g.iloc[:cut], g.iloc[cut:cut + H]
            for name, fn in MODELS.items():
                pred = fn(train, test.week_start)
                bt_rows.append(pd.DataFrame({"region": region, "fold": fold + 1, "model": name,
                                             "week_start": test.week_start.values,
                                             "actual": test.units.values, "forecast": pred}))
    bt = pd.concat(bt_rows, ignore_index=True)
    bt.to_csv(PROC / "backtest_predictions.csv", index=False)

    for (region, model), d in bt.groupby(["region", "model"]):
        d = d.dropna(subset=["forecast"])
        metric_rows.append({"region": region, "model": model,
                            "MAPE_%": mape(d.actual, d.forecast),
                            "WAPE_%": float(np.abs(d.actual - d.forecast).sum() / d.actual.sum() * 100),
                            "bias_%": float((d.forecast - d.actual).sum() / d.actual.sum() * 100),
                            "last_fold_MAPE_%": mape(d[d.fold == FOLDS].actual, d[d.fold == FOLDS].forecast)})
    met = pd.DataFrame(metric_rows).round(2)
    allm = bt.dropna(subset=["forecast"]).groupby("model").apply(
        lambda d: pd.Series({"MAPE_%": mape(d.actual, d.forecast)})).round(2)
    met.to_csv(PROC / "forecast_accuracy.csv", index=False)
    print(met.pivot(index="region", columns="model", values="MAPE_%"))
    print("overall\n", allm)

    # pick best non-baseline model per region, refit on all data, forecast 12 weeks
    out, chosen = [], {}
    for region, g in reg.groupby("region"):
        g = g.sort_values("week_start").reset_index(drop=True)
        cand = met[(met.region == region) & (met.model != "Seasonal naive")]
        best = cand.sort_values("MAPE_%").iloc[0].model
        chosen[region] = best
        fut = pd.date_range(g.week_start.max() + pd.Timedelta(weeks=1), periods=H, freq="7D")
        # prediction interval from backtest residuals of the chosen model
        res = bt[(bt.region == region) & (bt.model == best)]
        rel = (res.forecast / res.actual - 1)
        q_hi, q_lo = np.quantile(rel, [0.9, 0.1])  # forecast/actual - 1: over- and under-forecast tails
        fc = MODELS[best](g, fut)
        out.append(pd.DataFrame({"region": region, "week_start": fut, "model": best,
                                 "forecast": fc,
                                 "lower_80": fc / (1 + q_hi), "upper_80": fc / (1 + q_lo)}))
    fc = pd.concat(out, ignore_index=True)
    fc.to_csv(PROC / "forecast_next_12_weeks.csv", index=False)
    print(chosen)
    print(fc.groupby("region").forecast.agg(["sum", "mean", "max"]).round(0))


if __name__ == "__main__":
    main()
