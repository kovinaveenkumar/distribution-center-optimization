"""Build the (synthetic, documented-assumption) distribution network tables.

M5 only has state-level geography, so regions are anchored on each state's
main demand city. DC capacity / handling cost are ASSUMPTIONS sized so the
network is realistically tight (~85-90% utilised) - see README.
Shipping $/unit = fixed + per_100mi * great-circle miles / 100.
"""
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data"

DCS = pd.DataFrame([
    # dc, city, lat, lon, weekly capacity (units), handling $/unit
    ("DC1", "Phoenix, AZ", 33.45, -112.07, 100_000, 0.50),
    ("DC2", "Dallas, TX", 32.78, -96.80, 90_000, 0.55),
    ("DC3", "Chicago, IL", 41.88, -87.63, 95_000, 0.65),
    ("DC4", "Atlanta, GA", 33.75, -84.39, 80_000, 0.60),
], columns=["dc", "city", "lat", "lon", "weekly_capacity", "handling_cost_per_unit"])

REGIONS = pd.DataFrame([
    ("West", "Los Angeles, CA", 34.05, -118.24),
    ("South", "Houston, TX", 29.76, -95.37),
    ("Midwest", "Milwaukee, WI", 43.04, -87.91),
], columns=["region", "anchor_city", "lat", "lon"])

FIXED, PER_100MI = 0.15, 0.085


def haversine(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = (np.sin((lat2 - lat1) * p / 2) ** 2
         + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2)
    return 2 * 3958.8 * np.arcsin(np.sqrt(a))


def build():
    rows = []
    for _, r in REGIONS.iterrows():
        for _, d in DCS.iterrows():
            mi = haversine(r.lat, r.lon, d.lat, d.lon)
            rows.append((r.region, d.dc, round(mi), round(FIXED + PER_100MI * mi / 100, 3)))
    ship = pd.DataFrame(rows, columns=["region", "dc", "miles", "ship_cost_per_unit"])
    DATA.mkdir(exist_ok=True)
    DCS.to_csv(DATA / "dc_network.csv", index=False)
    REGIONS.to_csv(DATA / "regions.csv", index=False)
    ship.to_csv(DATA / "shipping_costs.csv", index=False)
    return DCS, REGIONS, ship


if __name__ == "__main__":
    d, r, s = build()
    print(d, "\n", s.pivot(index="region", columns="dc", values="ship_cost_per_unit"))
