"""Solve the EV charger siting model from FORMULATION.md with gurobipy-pandas.

Reads build/output/zcta_demand.csv written by 02_forecast_demand.py and builds
exactly the model documented in FORMULATION.md. For each (zcta, level):

    open   y  binary     whether a site of this level exists in the ZCTA
    count  x  integer    ports installed there (between the per-site min
                         and max if open, zero otherwise)
    served s  continuous EVs actually served, capped by the ports' realized
                         throughput (which depends on where the site is)

Level 2 and Level 3 sites in the same ZCTA draw down the same forecast EV
pool. Capital is a per-site fixed cost plus a per-port cost, against one
budget. The objective is the present value of revenue on EVs served.

`load_inputs()` and `build_model()` are importable for optional extensions
that build the same model and change one thing.

Output: build/output/solution.csv, one row per (zcta, level) actually built:
    zcta, level, count
and build/output/solution_detail.csv with the utilization, EVs served, capital,
and revenue behind each row.
"""

import json
from itertools import product
from pathlib import Path
from typing import cast

import gurobipy as gp
import gurobipy_pandas  # pyright: ignore  # noqa: F401  # registers the .gppd DataFrame accessor
import numpy as np
import pandas as pd
from constants import (
    ANNUAL_REVENUE_PER_EV,
    BUDGET,
    DISCOUNT_RATE,
    LEVELS,
    LIFETIME_REVENUE_FACTOR,
    MAX_PORTS_PER_SITE,
    MIN_PORTS_PER_SITE,
    PEAK_THROUGHPUT_PER_CHARGER,
    PORT_COST,
    SERVICE_LIFE_YEARS,
    SITE_FIXED_COST,
)
from gurobipy import GRB

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE.parent / "build" / "output"


def load_inputs(input_dir: Path = OUTPUT_DIR) -> pd.DataFrame:
    """One row per (zcta, level) with every parameter the model needs."""
    demand = pd.read_csv(input_dir / "zcta_demand.csv", dtype={"zcta": str})
    grid = pd.DataFrame(
        list(product(demand["zcta"], LEVELS)), columns=["zcta", "level"]
    ).merge(demand, on="zcta", how="left")
    level = grid["level"].astype(int)
    grid["utilization"] = [
        row[f"utilization_l{lvl}"] for lvl, (_, row) in zip(level, grid.iterrows())
    ]
    # k_{z,l}: EVs one port here serves per year, peak throughput scaled by
    # how busy the geography says this site would be.
    grid["throughput"] = (
        level.map(lambda lvl: PEAK_THROUGHPUT_PER_CHARGER[int(lvl)])
        * grid["utilization"]
    )
    grid["site_fixed_cost"] = level.map(lambda lvl: SITE_FIXED_COST[int(lvl)])
    grid["port_cost"] = level.map(lambda lvl: PORT_COST[int(lvl)])
    grid["min_ports"] = level.map(lambda lvl: MIN_PORTS_PER_SITE[int(lvl)])
    grid["max_ports"] = level.map(lambda lvl: MAX_PORTS_PER_SITE[int(lvl)])
    # Present value of serving one EV for the charger's whole service life.
    # LIFETIME_REVENUE_FACTOR is the discounted annuity factor, not the raw
    # year count: at 8% over 10 years it is 6.710.
    grid["lifetime_price"] = (
        level.map(lambda lvl: ANNUAL_REVENUE_PER_EV[int(lvl)]) * LIFETIME_REVENUE_FACTOR
    )
    return grid.set_index(["zcta", "level"])


def build_model(
    grid: pd.DataFrame, budget: float = BUDGET, name: str = "ev_charger_siting"
) -> tuple[gp.Model, pd.DataFrame, pd.DataFrame]:
    """Build the FORMULATION.md model. Returns (model, grid, per_zcta).

    `grid` comes back with variable columns `open`, `count`, `served` and
    constraint columns; `per_zcta` carries the shared demand-pool
    constraints. The budget constraint is `model.getConstrByName("budget")`.
    """
    model = gp.Model(name)
    grid = grid.copy()
    grid = grid.gppd.add_vars(model, vtype=GRB.BINARY, name="open")
    grid = grid.gppd.add_vars(model, vtype=GRB.INTEGER, name="count")
    grid = grid.gppd.add_vars(model, lb=0.0, obj="lifetime_price", name="served")
    model.ModelSense = GRB.MAXIMIZE
    model.update()

    # A port can't serve more EVs than its realized throughput allows.
    grid["capacity_expr"] = grid["throughput"] * grid["count"]
    grid = grid.gppd.add_constrs(
        model, "served", GRB.LESS_EQUAL, "capacity_expr", name="capacity"
    )

    # Site logic: no ports without a site; an open site has between the
    # per-site min and max ports.
    grid["max_expr"] = grid["max_ports"] * grid["open"]
    grid["min_expr"] = grid["min_ports"] * grid["open"]
    grid = grid.gppd.add_constrs(
        model, "count", GRB.LESS_EQUAL, "max_expr", name="site_max"
    )
    grid = grid.gppd.add_constrs(
        model, "count", GRB.GREATER_EQUAL, "min_expr", name="site_min"
    )

    # Level 2 and Level 3 in the same ZCTA share that ZCTA's forecast EVs.
    per_zcta = grid.groupby("zcta").agg(
        total_served=("served", "sum"),
        ev_forecast=("ev_forecast", "first"),
    )
    per_zcta = per_zcta.gppd.add_constrs(
        model, "total_served", GRB.LESS_EQUAL, "ev_forecast", name="demand_pool"
    )

    grid["capital_expr"] = (
        grid["site_fixed_cost"] * grid["open"] + grid["port_cost"] * grid["count"]
    )
    model.addConstr(grid["capital_expr"].sum() <= budget, name="budget")
    model.update()
    return model, grid, per_zcta


def extract_solution(grid: pd.DataFrame) -> pd.DataFrame:
    """Rows actually built, with the economics behind each."""
    built = grid.copy()
    built["count_x"] = built["count"].apply(lambda v: v.X)
    built = built.loc[built["count_x"] > 0.5].reset_index()
    built["count"] = built["count_x"].round().astype(int)
    built["served"] = built["served"].apply(lambda v: v.X)
    built["capacity"] = built["throughput"] * built["count"]
    built["capital"] = built["site_fixed_cost"] + built["port_cost"] * built["count"]
    built["revenue_npv"] = built["lifetime_price"] * built["served"]
    return built[
        [
            "zcta",
            "level",
            "count",
            "utilization",
            "throughput",
            "capacity",
            "served",
            "ev_forecast",
            "capital",
            "revenue_npv",
            "lat",
            "lon",
        ]
    ].sort_values(["zcta", "level"])


def nearest_chosen_site_miles(detail: pd.DataFrame) -> pd.Series:
    """For each built site, straight-line miles to the nearest other built site of the same level."""
    out = pd.Series(np.nan, index=detail.index)
    for _, rows in detail.groupby("level"):
        if len(rows) < 2:
            continue
        lat = np.radians(rows["lat"].to_numpy(dtype=float))
        lon = np.radians(rows["lon"].to_numpy(dtype=float))
        dlat = lat[:, None] - lat[None, :]
        dlon = lon[:, None] - lon[None, :]
        a = (
            np.sin(dlat / 2) ** 2
            + np.cos(lat[:, None]) * np.cos(lat[None, :]) * np.sin(dlon / 2) ** 2
        )
        dist = 3958.8 * 2 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
        np.fill_diagonal(dist, np.inf)
        out.loc[rows.index] = dist.min(axis=1)
    return out


def main(
    budget: float = BUDGET,
    input_dir: Path = OUTPUT_DIR,
    output_dir: Path = OUTPUT_DIR,
) -> None:
    grid = load_inputs(input_dir)
    model, grid, _ = build_model(grid, budget=budget)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "gurobi.log").unlink(missing_ok=True)
    model.Params.LogFile = str(output_dir / "gurobi.log")
    model.optimize()

    if model.Status != GRB.OPTIMAL:
        raise RuntimeError(f"Solve did not reach optimality (status {model.Status})")

    detail = extract_solution(grid)
    solution = cast(pd.DataFrame, detail[["zcta", "level", "count"]])
    output_dir.mkdir(parents=True, exist_ok=True)
    detail["nearest_new_site_mi"] = nearest_chosen_site_miles(detail)
    solution.to_csv(output_dir / "solution.csv", index=False)
    detail.round(4).to_csv(output_dir / "solution_detail.csv", index=False)

    spend = float(detail["capital"].to_numpy().sum())
    revenue_npv = float(model.ObjVal)
    print(
        f"\nWrote {len(solution)} (zcta, level, count) rows to {output_dir / 'solution.csv'}"
    )
    total_ports = int(solution["count"].to_numpy().sum())
    print(f"Chargers built: {total_ports} across {solution['zcta'].nunique()} ZCTAs")
    level_totals = cast(pd.Series, solution.groupby("level")["count"].sum())
    print(level_totals.to_string())
    print(f"Capital spent: ${spend:,.0f} of ${budget:,.0f} budget")
    print(
        f"Revenue NPV over {SERVICE_LIFE_YEARS} years "
        f"@ {DISCOUNT_RATE:.0%}: ${revenue_npv:,.0f}"
    )
    print(
        f"Solve: {model.Runtime:.2f}s, {int(model.NodeCount)} nodes, {model.IterCount:.0f} simplex iterations"
    )

    # Plausibility guard. Gross revenue is not profit (no electricity cost,
    # demand charges, or O&M here), so a healthy result is a low multiple of
    # capital, not a large one. v2 of this model returned 105x and nothing in
    # the pipeline objected, which is the failure this line exists to catch.
    ratio = revenue_npv / spend if spend else 0.0
    print(f"Gross revenue NPV per capital dollar: {ratio:.2f}x")
    if ratio > 5.0:
        print(
            "  WARNING: implausible for gross charging revenue. Check "
            "PEAK_THROUGHPUT_MULTIPLE and the price/throughput constants "
            "against physical charger capacity before trusting this solution."
        )

    # Whether each site is limited by its own ports or by local EVs tells
    # you whether the answer is about charger economics or about where the
    # EVs are.
    saturated = int((detail["capacity"] <= detail["served"] + 1e-6).sum())
    print(
        f"Sites running at full port capacity: {saturated} of {len(detail)} "
        f"(the rest are limited by local demand, not hardware)"
    )
    # Utilization is computed from EVs and *existing* ports around a site.
    # It does not know about the other sites this solve is opening, so two
    # new sites a few miles apart both count the same drivers. Report how
    # close the chosen sites are so that flaw is visible, not hidden.
    close = int((detail["nearest_new_site_mi"] < 5.0).sum())
    print(
        f"Sites within 5 miles of another new site of the same level: {close} of {len(detail)} "
        f"(utilization does not account for new sites competing with each other)"
    )
    print("\nWhere and how busy:")
    show = detail[
        [
            "zcta",
            "level",
            "count",
            "utilization",
            "served",
            "ev_forecast",
            "capital",
            "revenue_npv",
            "nearest_new_site_mi",
        ]
    ]
    print("  " + show.round(2).to_string(index=False).replace("\n", "\n  "))
    summary = {
        "budget": budget,
        "capital_spent": spend,
        "revenue_npv": revenue_npv,
        "ports": total_ports,
        "zctas": int(solution["zcta"].nunique()),
        "ports_by_level": {str(k): int(v) for k, v in level_totals.items()},
        "solver_version": ".".join(map(str, gp.gurobi.version())),
        "status": int(model.Status),
        "mip_gap": float(model.MIPGap),
        "input_directory": str(input_dir.relative_to(HERE.parent)),
        "objective": "discounted gross revenue; operating costs excluded",
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    model.dispose()


if __name__ == "__main__":
    main()
