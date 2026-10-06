# Build the Tableau Public dashboard (≈ 1–2 h)

Tableau Public needs your own login to publish, so this part is manual. All data is ready in `data/outputs/`.

1. Install **Tableau Public** (free) → *Connect → Text file* and add these four CSVs as separate data sources:
   | File | Grain | Used for |
   |---|---|---|
   | `tableau_demand_forecast.csv` | region × week × series (`Actual` / `Backtest forecast` / `Forecast`) | forecast vs actual |
   | `tableau_dc_utilization.csv` | scenario × demand_case × week × DC (has `utilization`, lat/lon) | how full each center runs |
   | `tableau_scenario_summary.csv` | scenario × demand_case | cost + savings per scenario |
   | `tableau_forecast_accuracy.csv` | region × model | MAPE table |
2. **Sheet 1 – Forecast vs actual:** Columns `week_start` (continuous), Rows `units`, Color `series`, filter/Panel by `region`. Add `lower_80`/`upper_80` as a band (dual-axis area is fine here because it is the *same* measure). Add a reference line at the last actual week.
3. **Sheet 2 – DC utilization:** bars of `AVG(utilization)` by `dc`, color by `dc`, filter `scenario` (single value, drives the dashboard) and `demand_case`. Add a constant reference line at 100%. Optional map using `lat`/`lon` sized by utilization.
4. **Sheet 3 – Scenario cost:** bars of `total` by `scenario` (filter `demand_case = base`), labels with `savings_vs_asis`. Add a second sheet for `breakeven_$per_unit_cap_wk`.
5. **Sheet 4 – Model accuracy:** highlight table of `MAPE_%` (region × model).
6. **Dashboard:** KPI row on top (total demand, cost per unit, savings %), forecast sheet full width, utilization + scenario cost side by side, scenario selector (parameter/filter) in one row above the charts. Add a text box with the recommendation from the README and the *synthetic network inputs* disclaimer.
7. *File → Save to Tableau Public*, copy the URL, and paste it into the README badge line.

Colours used in the repo charts (consistent palette): West `#2a78d6`, South `#eb6834`, Midwest `#1baf7a`; DC1–DC4 `#2a78d6 #eb6834 #1baf7a #eda100`.
