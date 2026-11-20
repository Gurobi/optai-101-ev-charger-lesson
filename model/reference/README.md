# Saved reference tables and plan.

These are the original course pipeline's saved outputs, copied unchanged
into lesson edition 0.1.0 on 2026-11-16. They describe 992 Michigan ZCTAs
and a $1 million capital scenario. These files allow a class to resume without preprocessing
or to inspect a solved plan without a solver license.

## Files and schemas.

| File | Rows / shape | Columns or keys |
|---|---|---|
| `zcta_features.csv` | 992 rows | zcta, population_2023, ev_2022, ev_2023, ev_current_est, existing_level2, existing_level3, lat, lon, land_area_sqmi |
| `zcta_demand.csv` | 992 rows | zcta, ev_forecast, remaining_demand, utilization_l2, utilization_l3, ev_per_port_l2, ev_per_port_l3, lat, lon |
| `solution.csv` | 12 rows | zcta, level, count |
| `solution_detail.csv` | 12 rows | zcta, level, count, utilization, throughput, capacity, served, ev_forecast, capital, revenue_npv, lat, lon |
| `gurobi.log` | Text | Solver log from re-solving this plan on 2026-11-17, with the local path and license lines removed |
| `state_context.json` | One object, 8 keys | afdc_bev_2025, afdc_phev_2025, ev_equivalents_2025, all_registered_vehicles_2025, statewide_zcta_population_2023, vehicles_per_resident, rescale_factor_2023_to_2025 |

## Meaning and derivation.

`zcta` is a five-digit text identifier. `population_2023` is the ACS
2019-2023 population estimate. `ev_2022` and `ev_2023` are joined SEMCOG
registration counts after exact-duplicate removal in 2022 and zero-filling
missing values. `ev_current_est` rescales the 2023 shares to
BEV_2025 + 0.4 * PHEV_2025 = 129,440 EV-equivalents. This preserves an
older geographic distribution as a teaching approximation, rather than
measuring present-day ZIP-level ownership. Scaling uses the joined table's
registration total. `existing_level2` and `existing_level3` count available
ports, including private-access stations. `lat` and `lon` are Census internal
points in decimal degrees; `land_area_sqmi` is land area in square miles.

`ev_forecast` is the discount-weighted average EV-equivalent count in a
conditional ten-year growth scenario. The empirical growth rate uses the
positive-count overlap of the two SEMCOG years, runs for three years, and
then tapers to 5% yearly. Population * vehicles_per_resident * 27% caps
each year's projection. `remaining_demand` subtracts existing capacity
at average throughput; it is retained as a historical diagnostic and is
not used by the current optimization model.

`ev_per_port_l2` and `ev_per_port_l3` are catchment EV-equivalents per
existing port plus one prospective port. Catchments weight distance by
exp(-miles / decay), with 3-mile and 12-mile scales. `utilization_l2` and
`utilization_l3` are dimensionless saturation values calibrated so the
existing-port-weighted mean utilization equals 0.4. Utilization uses only
existing competition and remains fixed while new sites are chosen.

`level` is 2 (AC) or 3 (DC fast); `count` is an integer number of ports.
`throughput` is EV-equivalents served per port per year after utilization;
`capacity` multiplies it by selected ports; `served` is the selected annual
EV-equivalent service amount. `capital` is fixed site cost plus per-port
installation cost, in dollars. `revenue_npv` is dollars of ten-year
discounted gross revenue at 8%, excluding operating costs. Detailed numeric
outputs are rounded to four decimal places.

Context keys with suffix 2025 hold statewide vehicle counts by fuel or
derived totals. `ev_equivalents_2025` applies the PHEV weight;
`all_registered_vehicles_2025` sums the AFDC fuel categories.
`statewide_zcta_population_2023` sums joined population;
`vehicles_per_resident` divides those two totals;
`rescale_factor_2023_to_2025` divides EV-equivalents by retained 2023
registrations. Sources span multiple vintages, not a synchronized survey.

The 12 baseline rows contain 142 Level 2 ports, $996,000 capital, and
$3,615,683.34 gross revenue NPV. Rounding in saved rows can affect the last
few cents. See the [formulation](../FORMULATION.md) for additional limitations.

Newly generated solutions add `nearest_new_site_mi` (straight-line miles
to another selected site of the same level) and `summary.json` with run
metadata. These are packaging/reporting additions; the archived original
files here remain unchanged.

Copyright © 2019 SEMCOG. All Rights Reserved. Reproduction or Use Without Permission is Prohibited.

Source conditions are in [LICENSE.md](LICENSE.md).
