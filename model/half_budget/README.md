# Saved half-budget plan.

The reference model reoptimized with a $500,000 budget, using the demand
table in `../reference/`.

Geography: Michigan ZCTAs. Input vintages: 2022/2023 registrations,
2023 ACS/Gazetteer, 2025 statewide registrations, 2026 station snapshot.
The demand projection is a conditional ten-year scenario. Dollar results
measure discounted gross revenue, with operating costs excluded.

Copyright © 2019 SEMCOG. All Rights Reserved. Reproduction or Use Without Permission is Prohibited.

## Files and schemas.

- `solution.csv`: 6 rows; columns: zcta, level, count.
- `solution_detail.csv`: 6 rows; columns: zcta, level, count, utilization, throughput, capacity, served, ev_forecast, capital, revenue_npv, lat, lon, nearest_new_site_mi.
- `gurobi.log`: solver log from re-solving this plan on 2026-11-17, with the local path and license lines removed.
- `summary.json`: JSON object with keys: budget, capital_spent, revenue_npv, ports, zctas, ports_by_level, solver_version, status, mip_gap, input_directory, objective.

See `../reference/README.md` for field meanings
and the transformation assumptions. See `../reference/LICENSE.md` for terms.

First solved 2026-11-16 with Gurobi 13.0.3. Re-solved 2026-11-17 with Gurobi
14.0.0, which chose the same plan; `summary.json` and `gurobi.log` are from
that run. The solve reached OPTIMAL within the default MIP gap tolerance.
