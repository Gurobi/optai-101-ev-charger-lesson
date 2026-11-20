"""ZCTA features -> forecast EV demand and location-dependent utilization.

This is the "where do the numbers come from" step: neither `d_z` nor
`u_{z,l}` in FORMULATION.md is a column in any raw dataset, so both have to
be built. Five parts:

1. Forecast each ZCTA's EV count forward across the charger's service life,
   using a statewide adoption-growth rate computed from real 2022->2023
   SEMCOG data, tapered to a long-run rate after a few years.
2. Cap each year's forecast at what the ZCTA's own vehicle fleet could
   plausibly hold. Some ZIP-level registration counts are inflated by
   fleet/corporate registrations at a business address, and uniform compound
   growth turns that into impossible demand without a ceiling.
3. Collapse the ten-year path to a single discount-weighted average, because
   the model is single-period. Weighting by the same discount rate the
   objective uses makes `d_z` the demand level whose constant revenue stream
   has the same present value as the real, growing one.
4. (v4) Compute, for each ZCTA and charger level, how busy a new port there
   would be: the EVs within driving range of the site, per existing port
   within the same range, run through a saturating curve and calibrated so
   the average existing Michigan port comes out at the measured statewide
   throughput. This is what makes one location worth more than another.
5. Keep v3's "remaining demand" (forecast net of what existing ports
   absorb) as a diagnostic column. v4's model does not use it: competition
   from existing ports now enters through utilization instead.

Output: build/output/zcta_demand.csv, one row per ZCTA:
    zcta, ev_forecast, remaining_demand, utilization_l2, utilization_l3,
    ev_per_port_l2, ev_per_port_l3, lat, lon
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from constants import (
    CATCHMENT_DECAY_MILES,
    DISCOUNT_RATE,
    EV_GROWTH_YEARS_AT_EMPIRICAL_RATE,
    LEVELS,
    LONG_RUN_ANNUAL_EV_GROWTH_RATE,
    MAX_EV_SHARE_OF_VEHICLE_FLEET,
    PEAK_THROUGHPUT_MULTIPLE,
    SERVICE_LIFE_YEARS,
    THROUGHPUT_PER_CHARGER,
)

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE.parent / "build" / "output"

EARTH_RADIUS_MILES = 3958.8


def empirical_growth_rate(features: pd.DataFrame) -> float:
    """Statewide 2022->2023 EV growth, on a like-for-like set of ZCTAs.

    The 2022 and 2023 SEMCOG layers don't cover the same ZIP sets: 78 ZIPs
    appear only in 2023. Dividing raw statewide totals counts those ZIPs as
    growth from zero and reports 51.7%, when the real like-for-like figure
    is 40.2%. Only ZCTAs with registrations in both years are compared.
    """
    both = features[(features["ev_2022"] > 0) & (features["ev_2023"] > 0)]
    rate = float(both["ev_2023"].sum() / both["ev_2022"].sum() - 1.0)
    naive = float(features["ev_2023"].sum() / features["ev_2022"].sum() - 1.0)
    print(
        f"Empirical statewide 2022->2023 EV growth: {rate:.1%} "
        f"(on the {len(both)} ZCTAs reporting both years; "
        f"the all-ZCTA figure of {naive:.1%} counts newly-reported ZIPs as growth)"
    )
    return rate


def growth_path(empirical_rate: float) -> list[float]:
    """Cumulative growth multiplier for each year of the service life.

    The empirical rate is an early-adoption figure. Applying it across a
    full ten-year horizon is what let v2 forecast more EVs than residents,
    so it runs for a few years and then tapers to a long-run rate.
    """
    fast_years = min(EV_GROWTH_YEARS_AT_EMPIRICAL_RATE, SERVICE_LIFE_YEARS)
    multipliers: list[float] = []
    for year in range(1, SERVICE_LIFE_YEARS + 1):
        fast = min(year, fast_years)
        slow = year - fast
        multipliers.append(
            (1.0 + empirical_rate) ** fast
            * (1.0 + LONG_RUN_ANNUAL_EV_GROWTH_RATE) ** slow
        )
    print(
        f"Growth path: {empirical_rate:.1%}/yr for {fast_years} years, then "
        f"{LONG_RUN_ANNUAL_EV_GROWTH_RATE:.1%}/yr -> "
        f"{multipliers[-1]:.2f}x by year {SERVICE_LIFE_YEARS}"
    )
    return multipliers


def pairwise_distance_miles(lat_deg: np.ndarray, lon_deg: np.ndarray) -> np.ndarray:
    """Great-circle distance between every pair of ZCTA internal points."""
    lat = np.radians(lat_deg)
    lon = np.radians(lon_deg)
    dlat = lat[:, None] - lat[None, :]
    dlon = lon[:, None] - lon[None, :]
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(lat[:, None]) * np.cos(lat[None, :]) * np.sin(dlon / 2) ** 2
    )
    return EARTH_RADIUS_MILES * 2 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def calibrate_saturation(
    ev_per_port: np.ndarray, port_weights: np.ndarray, target_mean: float
) -> float:
    """Find rho0 such that the port-weighted mean of 1 - exp(-rho/rho0) hits target_mean.

    The mean is taken over existing ports, so the calibration statement is
    "the average existing port realizes the measured statewide throughput."
    Monotone in rho0, so bisection is enough.
    """
    weights = port_weights / port_weights.sum()

    def weighted_mean(rho0: float) -> float:
        return float((weights * (1.0 - np.exp(-ev_per_port / rho0))).sum())

    lo, hi = 1e-3, 1e6
    for _ in range(200):
        mid = (lo * hi) ** 0.5
        if weighted_mean(mid) > target_mean:
            lo = mid
        else:
            hi = mid
    return (lo * hi) ** 0.5


def utilization_by_level(
    features: pd.DataFrame, ev_forecast: pd.Series, distance: np.ndarray
) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    """Per level: (ev_per_port, utilization) arrays aligned with `features`.

    Catchment EVs at a site are every ZCTA's forecast EVs weighted by
    exp(-distance / decay). Catchment ports are existing ports of the same
    level weighted the same way, plus one for the port being sited. Their
    ratio is the EVs a new port would compete for; the saturating curve
    turns that into a utilization in (0, 1).
    """
    result: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    target_mean = 1.0 / PEAK_THROUGHPUT_MULTIPLE
    for level in LEVELS:
        weights = np.exp(-distance / CATCHMENT_DECAY_MILES[level])
        existing = features[f"existing_level{level}"].to_numpy(dtype=float)
        catchment_evs = weights @ ev_forecast.to_numpy(dtype=float)
        catchment_ports = weights @ existing
        ev_per_port = catchment_evs / (catchment_ports + 1.0)
        rho0 = calibrate_saturation(ev_per_port, existing, target_mean)
        utilization = 1.0 - np.exp(-ev_per_port / rho0)
        realized = utilization * PEAK_THROUGHPUT_MULTIPLE
        port_weighted_mean = float((existing * realized).sum() / existing.sum())
        print(
            f"Level {level}: catchment decay {CATCHMENT_DECAY_MILES[level]:.0f} mi, "
            f"saturation at {rho0:,.0f} EVs/port; existing ports realize "
            f"{port_weighted_mean:.2f}x the measured average by construction; "
            f"best new site {utilization.max():.2f}, median {np.median(utilization):.2f}"
        )
        result[level] = (ev_per_port, utilization)
    return result


def main() -> None:
    features = pd.read_csv(OUTPUT_DIR / "zcta_features.csv", dtype={"zcta": str})
    context = json.loads((OUTPUT_DIR / "state_context.json").read_text())

    empirical_rate = empirical_growth_rate(features)
    multipliers = growth_path(empirical_rate)

    # Ceiling: a ZCTA can't hold more EVs than a plausible share of the
    # vehicles its residents own.
    vehicles_per_resident = float(context["vehicles_per_resident"])
    ev_ceiling = (
        features["population_2023"]
        * vehicles_per_resident
        * MAX_EV_SHARE_OF_VEHICLE_FLEET
    )

    # Discount-weighted average EV count over the service life. Year-1
    # demand counts for more than year-10 demand, matching the objective.
    weights = [
        1.0 / (1.0 + DISCOUNT_RATE) ** year for year in range(1, SERVICE_LIFE_YEARS + 1)
    ]
    weighted_sum = features["ev_current_est"] * 0.0
    for weight, multiplier in zip(weights, multipliers):
        capped_year = (features["ev_current_est"] * multiplier).clip(upper=ev_ceiling)
        weighted_sum = weighted_sum + weight * capped_year
    ev_forecast = weighted_sum / sum(weights)

    # v3 diagnostic: demand net of what existing ports absorb at the
    # measured average throughput. Not a model input in v4.
    existing_capacity = (
        features["existing_level2"] * THROUGHPUT_PER_CHARGER[2]
        + features["existing_level3"] * THROUGHPUT_PER_CHARGER[3]
    )
    already_served = existing_capacity.clip(upper=ev_forecast)
    remaining_demand = ev_forecast - already_served

    # v4: location-dependent utilization from the geography.
    print()
    distance = pairwise_distance_miles(
        features["lat"].to_numpy(dtype=float), features["lon"].to_numpy(dtype=float)
    )
    by_level = utilization_by_level(features, ev_forecast, distance)

    demand = pd.DataFrame(
        {
            "zcta": features["zcta"],
            "ev_forecast": ev_forecast,
            "remaining_demand": remaining_demand,
            "utilization_l2": by_level[2][1],
            "utilization_l3": by_level[3][1],
            "ev_per_port_l2": by_level[2][0],
            "ev_per_port_l3": by_level[3][0],
            "lat": features["lat"],
            "lon": features["lon"],
        }
    )

    out_path = OUTPUT_DIR / "zcta_demand.csv"
    demand.to_csv(out_path, index=False)

    # Diagnostics: the ceiling should bite a handful of ZCTAs, not most of
    # them. If it binds widely, either the growth path or the ceiling is
    # miscalibrated and the forecast deserves another look.
    final_year_uncapped = features["ev_current_est"] * multipliers[-1]
    capped = final_year_uncapped > ev_ceiling
    print(f"\nWrote {len(demand)} ZCTA rows to {out_path}")
    print(
        f"Statewide forecast EV-equivalents (discount-weighted): {ev_forecast.sum():,.0f}"
    )
    print(
        f"Statewide remaining demand after existing supply (v3 diagnostic): "
        f"{remaining_demand.sum():,.0f}"
    )
    print(
        f"ZCTAs hitting the {MAX_EV_SHARE_OF_VEHICLE_FLEET:.0%}-of-fleet ceiling: "
        f"{int(capped.sum())} of {len(features)}"
    )
    if capped.any():
        worst = features.loc[
            capped, ["zcta", "population_2023", "ev_current_est"]
        ].copy()
        worst["uncapped_year10"] = final_year_uncapped[capped]
        worst["ceiling"] = ev_ceiling[capped]
        worst["ev_per_1k_today"] = (
            1000 * worst["ev_current_est"] / worst["population_2023"]
        )
        print(
            "  "
            + worst.nlargest(5, "ev_per_1k_today")
            .to_string(index=False)
            .replace("\n", "\n  ")
        )

    print("\nBest DC fast sites by utilization (where a new port would be busiest):")
    top = demand.nlargest(8, "utilization_l3")[
        ["zcta", "ev_forecast", "ev_per_port_l3", "utilization_l3", "utilization_l2"]
    ].merge(features[["zcta", "existing_level2", "existing_level3"]], on="zcta")
    print("  " + top.round(2).to_string(index=False).replace("\n", "\n  "))


if __name__ == "__main__":
    main()
