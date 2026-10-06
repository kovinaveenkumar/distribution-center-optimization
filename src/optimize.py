"""Part 3 - weekly linear program: assign regional demand to DCs.

min   sum_{r,d} (ship[r,d] + handle[d]) * x[r,d]  +  PENALTY * overflow[r]
s.t.  sum_d x[r,d] + overflow[r] = demand[r]          (meet all demand)
      sum_r x[r,d] <= capacity[d] (+ added capacity)  (stay within capacity)
`overflow` is an explicit 3PL / spot-capacity lane at a high $/unit so the model is never
infeasible and any shortfall is quantified rather than hidden.

Scenarios (each run for the 12 forecast weeks, under base and high (upper-80) demand):
  0 As-is rule        : each region ships from its home DC, overflow spills pro-rata (cost-blind)
  1 Optimized         : LP on current capacity
  2 Optimized + DC1  : +30k units/wk at Phoenix
  3 Optimized + DC2  : +30k units/wk at Dallas
"""
from pathlib import Path

import pandas as pd
import pulp

from network import build

PROC = Path(__file__).resolve().parents[1] / "data" / "processed"
OUT = Path(__file__).resolve().parents[1] / "data" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

OVERFLOW_COST = 3.00          # $/unit 3PL / spot warehouse lane (assumption)
ADD_CAP = 30_000              # units/week added in expansion scenarios
EXPANSION_COST_PER_UNIT_WK = 0.40   # $ per added unit of weekly capacity per week (assumption)

dcs, regions, ship = build()
SHIP = {(r.region, r.dc): r.ship_cost_per_unit for r in ship.itertuples()}
HANDLE = dcs.set_index("dc").handling_cost_per_unit.to_dict()
CAP = dcs.set_index("dc").weekly_capacity.to_dict()
DC_IDS, REG_IDS = list(CAP), list(regions.region)
UNIT = {(r, d): SHIP[r, d] + HANDLE[d] for r in REG_IDS for d in DC_IDS}


def solve_lp(demand, cap):
    m = pulp.LpProblem("dc_assign", pulp.LpMinimize)
    x = pulp.LpVariable.dicts("x", UNIT.keys(), lowBound=0)
    o = pulp.LpVariable.dicts("o", REG_IDS, lowBound=0)
    m += pulp.lpSum(UNIT[k] * x[k] for k in UNIT) + OVERFLOW_COST * pulp.lpSum(o.values())
    for r in REG_IDS:
        m += pulp.lpSum(x[r, d] for d in DC_IDS) + o[r] == demand[r]
    for d in DC_IDS:
        m += pulp.lpSum(x[r, d] for r in REG_IDS) <= cap[d]
    m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[m.status] == "Optimal", pulp.LpStatus[m.status]
    flows = {k: x[k].value() for k in UNIT}
    over = {r: o[r].value() for r in REG_IDS}
    return flows, over


HOME = {"West": "DC1", "South": "DC2", "Midwest": "DC3"}


def solve_asis(demand, cap):
    """Status-quo rule (no optimizer): each region ships from its home DC; whatever exceeds the
    home DC's capacity is spilled pro-rata to the other DCs' spare capacity, ignoring cost."""
    left, flows, over = dict(cap), {k: 0.0 for k in UNIT}, {}
    for r in REG_IDS:                                   # home DCs first
        q = min(demand[r], left[HOME[r]])
        flows[r, HOME[r]] += q; left[HOME[r]] -= q
    for r in REG_IDS:                                   # then spill the remainder
        need = demand[r] - sum(flows[r, d] for d in DC_IDS)
        spare = sum(left.values())
        if need > 1e-9 and spare > 0:
            take = min(need, spare)
            for d in DC_IDS:
                flows[r, d] += take * left[d] / spare
            for d in DC_IDS:
                left[d] -= take * left[d] / spare
            need -= take
        over[r] = max(need, 0.0)
    return flows, over


def cost_of(flows, over):
    ship_c = sum(SHIP[k] * q for k, q in flows.items())
    hand_c = sum(HANDLE[k[1]] * q for k, q in flows.items())
    return ship_c, hand_c, OVERFLOW_COST * sum(over.values())


def main():
    fc = pd.read_csv(PROC / "forecast_next_12_weeks.csv", parse_dates=["week_start"])
    cases = {"base": "forecast", "high": "upper_80"}
    scen = {
        "0 As-is (home DC + pro-rata spill)": (solve_asis, 0, None),
        "1 Optimized - current capacity": (solve_lp, 0, None),
        "2 Optimized + 30k/wk at DC1 Phoenix": (solve_lp, ADD_CAP, "DC1"),
        "3 Optimized + 30k/wk at DC2 Dallas": (solve_lp, ADD_CAP, "DC2"),
    }
    assign, util, summ = [], [], []
    for case, col in cases.items():
        for sname, (fn, add, where) in scen.items():
            tot = dict(ship=0, hand=0, over_cost=0, over_units=0, expansion=0, demand=0)
            for wk, g in fc.groupby("week_start"):
                demand = g.set_index("region")[col].to_dict()
                cap = dict(CAP)
                if where:
                    cap[where] += add
                flows, over = fn(demand, cap)
                s, h, oc = cost_of(flows, over)
                tot["ship"] += s; tot["hand"] += h; tot["over_cost"] += oc
                tot["over_units"] += sum(over.values()); tot["demand"] += sum(demand.values())
                tot["expansion"] += add * EXPANSION_COST_PER_UNIT_WK if where else 0
                for (r, d), q in flows.items():
                    assign.append((case, sname, wk, r, d, q, q * SHIP[r, d], q * HANDLE[d]))
                for r, q in over.items():
                    assign.append((case, sname, wk, r, "3PL overflow", q, q * OVERFLOW_COST, 0.0))
                for d in DC_IDS:
                    used = sum(flows[r, d] for r in REG_IDS)
                    util.append((case, sname, wk, d, used, cap[d], used / cap[d]))
            tot["total"] = tot["ship"] + tot["hand"] + tot["over_cost"] + tot["expansion"]
            summ.append({"demand_case": case, "scenario": sname, **tot})
    assign = pd.DataFrame(assign, columns=["demand_case", "scenario", "week_start", "region", "dc",
                                           "units", "shipping_cost", "handling_cost"])
    util = pd.DataFrame(util, columns=["demand_case", "scenario", "week_start", "dc", "units_used",
                                       "capacity", "utilization"])
    summ = pd.DataFrame(summ)
    base0 = summ[summ.scenario.str.startswith("0")].set_index("demand_case").total
    summ["savings_vs_asis"] = summ.apply(lambda r: base0[r.demand_case] - r.total, axis=1)
    summ["savings_vs_asis_pct"] = summ.savings_vs_asis / summ.demand_case.map(base0) * 100
    summ["cost_per_unit"] = summ.total / summ.demand
    opt1 = summ[summ.scenario.str.startswith("1")].set_index("demand_case")
    # breakeven expansion price: max $/unit/wk of added capacity at which the expansion still pays
    summ["gross_saving_vs_opt1"] = summ.apply(
        lambda r: opt1.total[r.demand_case] - (r.total - r.expansion), axis=1)
    summ["breakeven_$per_unit_cap_wk"] = summ.apply(
        lambda r: r.gross_saving_vs_opt1 / (ADD_CAP * 12) if r.expansion > 0 else None, axis=1)
    assign.to_csv(OUT / "assignments.csv", index=False)
    util.to_csv(OUT / "dc_utilization.csv", index=False)
    summ.round(2).to_csv(OUT / "scenario_summary.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(summ.round(2)[["demand_case", "scenario", "demand", "total", "over_units", "expansion",
                          "savings_vs_asis", "savings_vs_asis_pct", "cost_per_unit",
                          "breakeven_$per_unit_cap_wk"]])
    u = util[(util.scenario.str.startswith("1"))].groupby(["demand_case", "dc"]).utilization.agg(["mean", "max"]).round(3)
    print(u)


if __name__ == "__main__":
    main()
