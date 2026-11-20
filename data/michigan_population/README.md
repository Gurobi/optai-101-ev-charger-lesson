# Michigan ZCTA population.

This archived ACS 5-Year population series comes from the U.S. Census Bureau.
The pipeline uses its 2023 vintage only.

## File and schema.

`michigan_zcta_population_2013_2023.csv` contains 5,932 rows across six
vintages (2013, 2015, 2017, 2019, 2021, 2023). Columns:

| Column | Meaning |
|---|---|
| `zcta` | Five-digit Census ZCTA identifier, stored as text |
| `year` | ACS release year |
| `population` | Total population estimate, ACS variable B01003_001E |
| `source` | Label identifying the ACS five-year reference window |

## Source and preparation.

Endpoint template:
`https://api.census.gov/data/{year}/acs/acs5?get=NAME,B01003_001E&for=zip%20code%20tabulation%20area:*`.
The archived table selects codes starting with 48 or 49 as the Michigan
working geography. Census sentinel values for uncomputable estimates were
converted to missing values during the original collection. The original
retrieval date was not recorded; this extraction does not invent one.

## Geography and time.

The 2013-2019 releases use 2010-vintage ZCTAs (987 selected codes); the
2021/2023 releases use 2020-vintage ZCTAs (992 selected codes). The 2023
estimate describes 2019-2023, rather than a single-year population count.
A prefix selection is a teaching shortcut, not a spatial intersection with
the Michigan boundary. ZCTAs approximate postal ZIP service areas, and a
same-code ZIP/ZCTA join is also a shortcut.

No decennial Census files are included because the lesson does not use them.
See [LICENSE.md](LICENSE.md) for source terms.
