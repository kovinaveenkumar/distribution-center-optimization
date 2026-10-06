-- Queries used in notebooks/01_explore_clean.ipynb (SQLite: data/processed/supply_chain.db)

-- Q1: yearly volume and growth by region
SELECT region, substr(week_start,1,4) AS yr, SUM(units) AS units,
       ROUND(100.0 * (SUM(units) - LAG(SUM(units)) OVER (PARTITION BY region ORDER BY substr(week_start,1,4)))
             / LAG(SUM(units)) OVER (PARTITION BY region ORDER BY substr(week_start,1,4)), 1) AS yoy_pct
FROM region_weekly
GROUP BY region, yr;

-- Q2: seasonality index = avg weekly units in month / avg weekly units overall (2012-2015 full years)
SELECT region, CAST(substr(week_start,6,2) AS INT) AS month,
       ROUND(AVG(units) / (SELECT AVG(units) FROM region_weekly r2 WHERE r2.region = r.region
                            AND substr(week_start,1,4) BETWEEN '2012' AND '2015'), 3) AS seasonal_index
FROM region_weekly r
WHERE substr(week_start,1,4) BETWEEN '2012' AND '2015'
GROUP BY region, month;

-- Q3: share of each store in its region (concentration)
SELECT region, store_id, SUM(units) AS units,
       ROUND(100.0 * SUM(units) / SUM(SUM(units)) OVER (PARTITION BY region), 1) AS pct_of_region
FROM store_weekly GROUP BY region, store_id;

-- Q4: data-quality: weeks per region (should all be equal)
SELECT region, COUNT(*) AS weeks, MIN(week_start) AS first_week, MAX(week_start) AS last_week
FROM region_weekly GROUP BY region;

-- Q5: category mix per region (last 52 weeks)
SELECT region, cat_id, SUM(units) AS units,
       ROUND(100.0 * SUM(units) / SUM(SUM(units)) OVER (PARTITION BY region), 1) AS pct
FROM category_weekly
WHERE week_start >= (SELECT date(MAX(week_start), '-364 days') FROM category_weekly)
GROUP BY region, cat_id;
