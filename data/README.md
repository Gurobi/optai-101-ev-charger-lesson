# Data sources.

These are the four source datasets the model uses, as collected for lesson
edition 0.1.0. They stay unchanged during a lesson. The
[journey](../journey/README.md) shows how they were found. Tables derived
from them, and the saved plans, are in
[model/reference/](../model/reference/README.md).

## Source inventory.

| Dataset folder | Included rows | Time and use |
|---|---:|---|
| `michigan_ev_charger_locations` | 2,127 stations | AFDC snapshot collected 2026-08-17; available-port supply and published prices |
| `michigan_ev_registration` | 891 + 958 ZIP rows; 12 statewide fuel rows | SEMCOG layers labeled 2022 and 2023; AFDC 2025 statewide counts |
| `michigan_population` | 5,932 rows across six vintages | ACS5 2013/2015/2017/2019/2021/2023; pipeline uses the 992 rows from 2023 |
| `michigan_zcta_centroids` | 992 ZCTAs | 2023 Gazetteer internal points and land/water areas |

Each folder contains its exact schema and dimensions in `README.md` and its
legal record in `LICENSE.md`. Derived tables retain the source terms. There
is no single license that replaces these dataset-specific conditions.

## Find the original sources.

- [AFDC station download](https://afdc.energy.gov/data_download): select
  Michigan and electric fuel. The archive contains the full statewide
  public/private export, including planned and temporarily unavailable
  stations; the model counts available stations only.
- [SEMCOG 2023 registration layer](https://services1.arcgis.com/xUx8EjNc6egUPYWh/arcgis/rest/services/MIEVRegbyZIPCode2023/FeatureServer/0).
- [SEMCOG 2022 registration layer](https://gis.semcog.org/server/rest/services/Hosted/MIEVRegbyZIPCode2022/FeatureServer/38).
- [AFDC Michigan statewide registrations](https://afdc.energy.gov/vehicle-registration).
- [Census ACS API](https://api.census.gov/data/2023/acs/acs5): total
  population B01003_001E by ZCTA.
- [Census 2023 Gazetteer](https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_zcta_national.zip).

Current downloads may differ from this lesson edition. Data discovery does
not require replacing the archive, obtaining keys, or refreshing a whole
state during class. Optional refresh work belongs to a new reviewed edition.

## Data choices to discuss.

The lesson matches ZIP and ZCTA by code, uses prefix-based working geography,
zero-fills unreported registrations, estimates 2025 local EV counts from
older geographic shares, and combines sources of different vintages. These
choices are recorded assumptions rather than properties certified by a
publisher. The full pipeline and formulation explain them.

The ACS population is a five-year estimate. Census internal points are
representative positions within polygons, rather than population-weighted
centroids. Source labels and update timestamps do not automatically prove a
registration layer's actual measurement date.

Tourism datasets, the undated registration layer, decennial Census files,
and the one-shot comparison models' data are excluded because the lesson
does not need them.

## Attribution.

Copyright © 2019 SEMCOG. All Rights Reserved. Reproduction or Use Without Permission is Prohibited.

SEMCOG's agreement grants distribution and derivative-work rights subject
to its conditions, including this notice. AFDC's station download terms
permit use for any purpose and address distribution. Census federal data is
public domain. The AFDC statewide-registration CSV is a factual extract
of published Michigan counts. See the dataset LICENSE files for details.
No publisher endorses this lesson's recommendation.
