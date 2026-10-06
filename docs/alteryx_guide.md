# Rebuild Part 1 (data prep) in Alteryx Designer

**Goal:** reproduce `src/prepare_data.py` as an Alteryx workflow (`alteryx/part1_data_prep.yxmd`) and prove it matches the Python output. Do this yourself in Designer; only list Alteryx on your resume once you have built and run it.

**Getting Designer:** it is Windows-only. Options: Alteryx Designer free trial (30 days) on a Windows PC or VM (you already have VirtualBox), or the free *Designer Core* training on Alteryx Academy (it gives you a learning licence).

## Inputs
* `data/raw/sales_train_evaluation.csv` (30,490 rows × `id,item_id,dept_id,cat_id,store_id,state_id,d_1…d_1941`)
* `data/raw/calendar.csv` (`date, wm_yr_wk, d, …`)

## Workflow (≈ 10 tools)
| # | Tool | Configuration | Purpose |
|---|---|---|---|
| 1 | **Input Data** | sales_train_evaluation.csv | wide item-day sales |
| 2 | **Summarize** | Group by `store_id`; Sum of every `d_*` column | 30,490 item rows → 10 store rows |
| 3 | **Transpose** | Key = `store_id`; data columns = all `d_*` | store × day long format (`Name`=day, `Value`=units) → 19,410 rows |
| 4 | **Input Data** | calendar.csv | |
| 5 | **Join** | `Name` = `d` (left: transposed, right: calendar) | adds `date`, `wm_yr_wk` |
| 6 | **Summarize** | Group by `store_id`, `wm_yr_wk`; Min of `date` → `week_start`; Count of `date` → `days`; Sum of `Value` → `units` | store-week |
| 7 | **Filter** | `[days] = 7` | drop partial first/last weeks → **2,770 rows** |
| 8 | **Formula** | `region = IF Left([store_id],2)="CA" THEN "West" ELSEIF Left([store_id],2)="TX" THEN "South" ELSE "Midwest" ENDIF` | state → region |
| 9 | **Summarize** | Group by `region`, `week_start`; Sum of `units` | region-week |
| 10 | **Sort** → **Output Data** | `region`, `week_start` → `alteryx/regional_weekly_volume_alteryx.csv` | |

Tips: in tool 3 you may need a *Select* tool first to drop `id` etc.; the `Name` column holds text such as `d_1`. Cast `Value` to Int32/Double, `date` to Date.

## Validate against the Python output
Your result must match `data/processed/regional_weekly_volume.csv` exactly:

| Check | Expected |
|---|---|
| Rows | **831** (277 weeks × 3 regions) |
| Store-week rows after tool 7 | **2,770** |
| Total units | **66,821,317** |
| Sum of units by region | West **29,148,970**, South **19,199,909**, Midwest **18,472,438** |
| West, week_start 2011-01-29 | 82,653 |
| West, last week 2016-05-14 | 131,017 |

## Optional extras (nice for the resume story)
* Add a **Browse** tool after tool 9 and screenshot the output into `assets/alteryx_workflow.png`.
* Use a **Workflow → Documentation** (Layout) note to label each stage.
* Put the `.yxmd` and the screenshot in an `alteryx/` folder, commit, and add one README line: "Part 1 data prep also implemented as an Alteryx workflow (validated row-for-row against the pandas pipeline)."
