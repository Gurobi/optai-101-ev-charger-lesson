# Michigan ZCTA centroids and land area

One row per Michigan ZIP Code Tabulation Area (ZCTA): its internal point
(a representative latitude/longitude inside the polygon) and its land and
water area. This is the geography the EV siting model needs to say how
far apart two ZCTAs are, which is what lets a charger's expected
utilization depend on the EVs and existing ports around it rather than
only on the ZCTA it sits in. Full license text and terms: [`LICENSE.md`](LICENSE.md).

## Files

- **`michigan_zcta_centroids_2023.csv`**: 992 rows, one per Michigan
  ZCTA. Filtered on 2026-09-09 from the Census Bureau's 2023 national
  ZCTA Gazetteer file
  (`2023_Gaz_zcta_national.zip` at
  `https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/`)
  to GEOIDs beginning `48` or `49`. Michigan ZIP codes are exclusively in
  the 480xx-499xx range, so this filter captures the whole state with no
  cross-state contamination.

## Columns

| Column | Source field | Meaning |
|---|---|---|
| `zcta` | `GEOID` | Five-digit ZCTA code, kept as a string |
| `land_area_sqmi` | `ALAND_SQMI` | Land area in square miles |
| `water_area_sqmi` | `AWATER_SQMI` | Water area in square miles |
| `lat` | `INTPTLAT` | Latitude of the internal point, decimal degrees |
| `lon` | `INTPTLONG` | Longitude of the internal point, decimal degrees |

The two raw square-meter area fields (`ALAND`, `AWATER`) were dropped as
redundant with the square-mile columns.

## Dimensionality

- **Geography:** 992 Michigan ZCTAs on 2020-vintage boundaries, the same
  set the 2021 and 2023 ACS population vintages in
  [`../michigan_population/`](../michigan_population/) use. Every ZCTA in
  the pipeline's feature table has a centroid here and vice versa
  (checked 2026-09-09).
- **Time:** a single vintage. ZCTA boundaries change only with the
  decennial census, so these points are stable through the 2020s.
- **Extent:** latitude 41.73 to 47.44, longitude -90.13 to -82.46. Land
  area runs from 0.01 to 706.5 square miles (median 37.0).

## Known quirks

- The **2020** Gazetteer release lists 987 Michigan ZCTAs; the 2023
  release lists 992. The 2023 file matches the ZCTA set in the population
  and registration pipeline, which is why it was chosen over the
  nominally more "2020" file.
- An internal point is not a population-weighted centroid. For large
  rural ZCTAs (several hundred square miles) the point can sit far from
  where people live. Distances between neighboring ZCTAs are
  approximate at the scale of a few miles.
- Straight-line distance between internal points is used downstream, not
  road distance.
