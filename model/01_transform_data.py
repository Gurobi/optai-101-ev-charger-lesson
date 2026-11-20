"""Raw shared-data CSVs -> one tidy ZCTA-level feature table.

Reads directly from `data/`, the same files documented and
licensed in that folder's per-dataset READMEs. Joins ZIP codes to ZCTAs by
treating the 5-digit code as the same key in both. ZCTAs approximate ZIP
service areas, but do not share identical boundaries. The source population
and internal-point tables use prefixes 48 and 49 as working geography rather
than a spatial intersection. These are teaching shortcuts, not a guarantee
about postal or state-boundary membership. Missing counts become zero as an
explicit assumption.

Output: build/output/zcta_features.csv, one row per Michigan ZCTA:
    zcta, population_2023, ev_2022, ev_2023, ev_current_est,
    existing_level2, existing_level3, lat, lon, land_area_sqmi
"""

import json
from pathlib import Path
from typing import cast

import pandas as pd
from constants import PHEV_PUBLIC_CHARGING_EQUIVALENT

HERE = Path(__file__).resolve().parent
SHARED_DATA = HERE.parent / "data"
OUTPUT_DIR = HERE.parent / "build" / "output"


def load_population() -> pd.DataFrame:
    path = (
        SHARED_DATA / "michigan_population" / "michigan_zcta_population_2013_2023.csv"
    )
    raw = pd.read_csv(path, dtype={"zcta": str})
    year_2023 = raw.loc[raw["year"] == 2023, ["zcta", "population"]]
    return year_2023.rename(columns={"population": "population_2023"})


def load_ev_registration_2023() -> pd.DataFrame:
    path = (
        SHARED_DATA
        / "michigan_ev_registration"
        / "michigan_ev_registration_by_zip_semcog_2023.csv"
    )
    raw = pd.read_csv(path, dtype={"ZIP_CODE": str})
    renamed = raw.rename(columns={"ZIP_CODE": "zcta", "FREQUENCY": "ev_2023"})
    renamed["ev_2023"] = renamed["ev_2023"].fillna(0)
    grouped = renamed.groupby("zcta", as_index=False).agg(ev_2023=("ev_2023", "sum"))
    return grouped


def load_ev_registration_2022() -> pd.DataFrame:
    # Known quirk (see michigan_ev_registration/README.md): this layer
    # contains 3 ZIPs duplicated as exact-duplicate rows. Drop full-row
    # duplicates before summing so those 3 ZIPs aren't double-counted.
    path = (
        SHARED_DATA
        / "michigan_ev_registration"
        / "michigan_ev_registration_by_zip_semcog_2022.csv"
    )
    raw = pd.read_csv(path, dtype={"zip": str}).drop_duplicates()
    renamed = raw.rename(columns={"zip": "zcta", "frequency": "ev_2022"})
    renamed["ev_2022"] = renamed["ev_2022"].fillna(0)
    grouped = renamed.groupby("zcta", as_index=False).agg(ev_2022=("ev_2022", "sum"))
    return grouped


def load_state_registration_totals_2025() -> dict[str, float]:
    """Statewide 2025 registrations by fuel type, plus two derived totals.

    `ev_equivalents` counts PHEVs at a fraction of a BEV
    (PHEV_PUBLIC_CHARGING_EQUIVALENT) because they charge publicly far less.
    `all_vehicles` is every fuel type summed, used downstream to bound how
    many EVs a ZCTA's vehicle fleet could plausibly contain.
    """
    path = (
        SHARED_DATA
        / "michigan_ev_registration"
        / "michigan_ev_registration_state_totals_afdc.csv"
    )
    raw = pd.read_csv(path)
    counts: list[float] = raw["registered_count"].astype(float).tolist()
    fuels: list[str] = raw["fuel_type"].astype(str).tolist()
    by_fuel = dict(zip(fuels, counts))
    bev = by_fuel["Electric (EV)"]
    phev = by_fuel["Plug-In Hybrid Electric (PHEV)"]
    return {
        "bev": bev,
        "phev": phev,
        "ev_equivalents": bev + PHEV_PUBLIC_CHARGING_EQUIVALENT * phev,
        "all_vehicles": sum(counts),
    }


def load_centroids() -> pd.DataFrame:
    # Census Gazetteer internal points, 2020-vintage ZCTA boundaries, the
    # same set the 2021/2023 ACS population vintages use. Straight-line
    # distance between these points is how v4 decides which ZCTAs are in
    # a site's catchment.
    path = SHARED_DATA / "michigan_zcta_centroids" / "michigan_zcta_centroids_2023.csv"
    raw = pd.read_csv(path, dtype={"zcta": str})
    return cast(pd.DataFrame, raw[["zcta", "lat", "lon", "land_area_sqmi"]])


def load_existing_chargers() -> pd.DataFrame:
    # Only Status Code == "E" (available now) counts as supply competing
    # for demand today -- planned ("P") and temporarily-unavailable ("T")
    # stations aren't live competition.
    path = (
        SHARED_DATA
        / "michigan_ev_charger_locations"
        / "michigan_ev_charger_locations.csv"
    )
    raw = pd.read_csv(path, dtype={"ZIP": str})
    available = raw.loc[raw["Status Code"] == "E"]
    renamed = available.rename(
        columns={
            "ZIP": "zcta",
            "EV Level2 EVSE Num": "existing_level2",
            "EV DC Fast Count": "existing_level3",
        }
    )
    renamed["existing_level2"] = renamed["existing_level2"].fillna(0)
    renamed["existing_level3"] = renamed["existing_level3"].fillna(0)
    return renamed.groupby("zcta", as_index=False).agg(
        existing_level2=("existing_level2", "sum"),
        existing_level3=("existing_level3", "sum"),
    )


def main() -> None:
    population = load_population()
    ev_2023 = load_ev_registration_2023()
    ev_2022 = load_ev_registration_2022()
    chargers = load_existing_chargers()
    centroids = load_centroids()
    state_totals = load_state_registration_totals_2025()

    # Population is the most complete ZCTA list (~987-992 statewide), so it
    # anchors the join. A ZCTA absent from a registration or charger file
    # is treated as 0 for that column -- per the registration README, a
    # null there isn't guaranteed to be a true zero, but for this demo's
    # feature table, "no rows reported" and "no rows recorded" are treated
    # the same way.
    features = population.merge(ev_2023, on="zcta", how="left")
    features = features.merge(ev_2022, on="zcta", how="left")
    features = features.merge(chargers, on="zcta", how="left")
    features = features.merge(centroids, on="zcta", how="left")
    if bool(features["lat"].isna().any()):
        missing = features.loc[features["lat"].isna(), "zcta"].tolist()
        raise RuntimeError(f"{len(missing)} ZCTAs have no centroid: {missing[:10]}")
    for col in ["ev_2023", "ev_2022", "existing_level2", "existing_level3"]:
        features[col] = features[col].fillna(0)

    # Documented rescaling approach (see michigan_ev_registration/README.md
    # "Rescaling approach"): scale each ZCTA's 2023 share by the ratio of
    # the current statewide AFDC total to the 2023 snapshot's own total,
    # to get a modern per-ZCTA EV estimate. Assumes the geographic
    # distribution of ownership hasn't shifted materially since 2023.
    #
    # The statewide target counts PHEVs at a fraction of a BEV rather than
    # ignoring them: they charge publicly, just much less. SEMCOG's layer
    # doesn't split BEV from PHEV, so the weighting is applied to the
    # statewide total and the ZCTA shares carry the geography.
    ev_equivalents_2025 = state_totals["ev_equivalents"]
    rescale_factor = ev_equivalents_2025 / features["ev_2023"].sum()
    features["ev_current_est"] = features["ev_2023"] * rescale_factor

    features = features[
        [
            "zcta",
            "population_2023",
            "ev_2022",
            "ev_2023",
            "ev_current_est",
            "existing_level2",
            "existing_level3",
            "lat",
            "lon",
            "land_area_sqmi",
        ]
    ]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "zcta_features.csv"
    features.to_csv(out_path, index=False)

    # Statewide scalars the demand step needs but that aren't per-ZCTA
    # columns. Vehicles per resident bounds how many EVs a ZCTA's own fleet
    # could hold, which is what stops fleet-registration artifacts from
    # producing more EVs than a ZCTA has vehicles.
    statewide_population = float(features["population_2023"].astype(float).sum().item())
    context = {
        "afdc_bev_2025": state_totals["bev"],
        "afdc_phev_2025": state_totals["phev"],
        "ev_equivalents_2025": ev_equivalents_2025,
        "all_registered_vehicles_2025": state_totals["all_vehicles"],
        "statewide_zcta_population_2023": statewide_population,
        "vehicles_per_resident": state_totals["all_vehicles"] / statewide_population,
        "rescale_factor_2023_to_2025": rescale_factor,
    }
    context_path = OUTPUT_DIR / "state_context.json"
    context_path.write_text(json.dumps(context, indent=2) + "\n")

    print(f"Wrote {len(features)} ZCTA rows to {out_path}")
    print(f"Wrote statewide context to {context_path}")
    print(
        f"AFDC 2025: {state_totals['bev']:,.0f} BEV + {state_totals['phev']:,.0f} PHEV "
        f"-> {ev_equivalents_2025:,.0f} EV-equivalents"
    )
    print(f"2023 SEMCOG ZCTA-level total: {features['ev_2023'].sum():,.0f}")
    print(f"Rescale factor applied: {rescale_factor:.3f}")
    print(
        f"Statewide vehicles per resident: {context['vehicles_per_resident']:.2f} "
        f"({state_totals['all_vehicles']:,.0f} vehicles / "
        f"{statewide_population:,.0f} residents)"
    )


if __name__ == "__main__":
    main()
