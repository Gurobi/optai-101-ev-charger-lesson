# Michigan EV registrations.

The two SEMCOG ZIP-level snapshots describe the distribution of EV
registrations used to estimate demand. The AFDC statewide total provides
a later scale. The SEMCOG files preserve source schemas and quirks.

## Files, exact schemas, and dimensions.

| File | Rows | Columns |
|---|---:|---|
| `michigan_ev_registration_by_zip_semcog_2022.csv` | 891 | zip, city, frequency |
| `michigan_ev_registration_by_zip_semcog_2023.csv` | 958 | ZIP_CODE, PO_NAME, FREQUENCY |
| `michigan_ev_registration_state_totals_afdc.csv` | 12 | year, fuel_type, registered_count |

ZIP fields are five-digit identifiers stored as text. `city` and `PO_NAME`
are locality labels. `frequency` and `FREQUENCY` are recorded registration
counts, which may be missing. In the statewide file, `year` identifies 2025,
`fuel_type` names the category, and `registered_count` is its vehicle total.
The ZIP sets differ between years. These are separate snapshots, not a
consistent panel or a synchronized census of charging demand.

## Sources and collection.

All three files were collected 2026-08-17.

- [2022 SEMCOG feature layer](https://gis.semcog.org/server/rest/services/Hosted/MIEVRegbyZIPCode2022/FeatureServer/38).
- [2023 SEMCOG feature layer](https://services1.arcgis.com/xUx8EjNc6egUPYWh/arcgis/rest/services/MIEVRegbyZIPCode2023/FeatureServer/0).
- [AFDC 2025 registration table](https://afdc.energy.gov/vehicle-registration).
  The lesson transcribes the rounded Michigan counts by fuel type into its
  own CSV schema. The table reports statewide totals without a ZIP breakdown.

The full original query strings were not retained; the archived files
fix the edition used for teaching.

## Quirks and transformation assumptions.

The 2022 `frequency` sum is 30,133 across 766 non-null rows before
deduplication. ZIPs 48309, 48866, and 49336 each contain an exact duplicate
source row. Stage 01 removes full-row duplicates before aggregation.
The 2023 `FREQUENCY` sum is 45,414 across 827 non-null rows. A missing
registration count does not establish that an area has no EVs.

The pipeline anchors the join to 2023 ACS population ZCTAs, matches ZIP
and ZCTA digit strings, and fills missing registration counts with zero.
Unmatched source ZIPs are dropped. Those choices are explicit approximations.
The growth estimate uses ZCTAs with positive registration counts in both
years rather than treating newly reported ZIPs as growth from zero.

For each retained ZCTA, the estimated baseline is:

```text
ev_equivalents_2025 = BEV_2025 + 0.4 * PHEV_2025
zip_estimate_2025 = zip_count_2023 * ev_equivalents_2025 / sum(joined_zip_counts_2023)
```

The PHEV weight is a public-charging-demand assumption. Rescaling assumes
the older geographic distribution remains informative; the result is a
derived estimate rather than a measured 2025 ZIP count. Stage 02 projects
this estimate forward and imposes a population-based vehicle-fleet ceiling.
The undated SEMCOG source layer is excluded from this lesson.

Copyright © 2019 SEMCOG. All Rights Reserved. Reproduction or Use Without Permission is Prohibited.

Source terms and the basis for sharing the AFDC extract are in [LICENSE.md](LICENSE.md).
