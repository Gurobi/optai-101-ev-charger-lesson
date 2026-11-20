# Michigan EV charging station locations

Every public and private EV charging station location in Michigan currently
listed on the NREL/DOE Alternative Fuels Data Center (AFDC).

## Files

- **`michigan_ev_charger_locations.csv`** : 2,127 rows, one per charging
  station location. Pulled 2026-08-17 from the AFDC bulk download
  (`fuel_type=ELEC`, `state=MI`). All rows are Michigan (`State == "MI"`),
  all rows are electric (`Fuel Type Code == "ELEC"`).

## Columns

The file carries AFDC's full standard station schema (columns not used for
this course are still present, left as-is):

- **Identity/location:** `ID`, `Station Name`, `Street Address`,
  `Intersection Directions`, `City`, `State`, `ZIP`, `Plus4`, `Country`,
  `Latitude`, `Longitude`, `Geocode Status`.
- **Network/ownership:** `EV Network`, `EV Network Web`, `Owner Type Code`,
  `Station Phone`, `Federal Agency ID`/`Federal Agency Name`/`Federal Agency
  Code` (blank unless federally owned).
- **Charging hardware:** `EV Level1 EVSE Num`, `EV Level2 EVSE Num`, `EV DC
  Fast Count`, `EV Connector Types`, `EV Pricing`, `EV Workplace Charging`,
  `EV On-Site Renewable Source`, `EV Other Info`.
- **Status/lifecycle:** `Status Code` (`E` = available, `T` = temporarily
  unavailable, `P` = planned), `Expected Date`, `Open Date`, `Date Last
  Confirmed`, `Updated At`, `Access Code`, `Access Days Time`, `Access
  Detail Code`, `Groups With Access Code`, `Restricted Access`.
- **Non-electric fuel columns** (present in every AFDC export, always blank
  for this file since every row is `ELEC`): the `NG *`, `CNG *`, `LNG *`,
  `LPG *`, `BD *`, `RD *`, `E85 *`, `Hydrogen *` columns, plus their French
  (Quebec-market) translation counterparts, `NPS Unit Name`, `Maximum
  Vehicle Class`, `Funding Sources`.

## Dimensionality

- **Geography:** statewide Michigan, 2,127 station locations (point
  locations with lat/long, not aggregated to ZIP or county).
- **Time:** a point-in-time snapshot as of the pull date (2026-08-17), not
  a time series. `Open Date` spans 2011-04-15 through 2026-08-15; `Date
  Last Confirmed` spans 2022-05-05 through 2026-08-17 (AFDC's own
  recency-verification field, not a re-pull date).
- **Networks represented (top 5 by station count):** ChargePoint Network
  (1,002), RED_E (435), Non-Networked (273), Blink Network (81), Tesla
  Destination (59) : plus a long tail of smaller networks (EV Connect,
  Tesla, FORD_CHARGE, FLO, RIVIAN_WAYPOINTS, etc.).
- **Status breakdown:** 2,062 available (`E`), 52 temporarily unavailable
  (`T`), 13 planned (`P`).

See [`LICENSE.md`](LICENSE.md) for source and license terms.

## Exact CSV header.

```text
Fuel Type Code
Station Name
Street Address
Intersection Directions
City
State
ZIP
Plus4
Station Phone
Status Code
Expected Date
Groups With Access Code
Access Days Time
Cards Accepted
BD Blends
NG Fill Type Code
NG PSI
EV Level1 EVSE Num
EV Level2 EVSE Num
EV DC Fast Count
EV Other Info
EV Network
EV Network Web
Geocode Status
Latitude
Longitude
Date Last Confirmed
ID
Updated At
Owner Type Code
Federal Agency ID
Federal Agency Name
Open Date
Hydrogen Status Link
NG Vehicle Class
LPG Primary
E85 Blender Pump
EV Connector Types
Country
Intersection Directions (French)
Access Days Time (French)
BD Blends (French)
Groups With Access Code (French)
Hydrogen Is Retail
Access Code
Access Detail Code
Federal Agency Code
Facility Type
CNG Dispenser Num
CNG On-Site Renewable Source
CNG Total Compression Capacity
CNG Storage Capacity
LNG On-Site Renewable Source
E85 Other Ethanol Blends
EV Pricing
EV Pricing (French)
LPG Nozzle Types
Hydrogen Pressures
Hydrogen Standards
CNG Fill Type Code
CNG PSI
CNG Vehicle Class
LNG Vehicle Class
EV On-Site Renewable Source
Restricted Access
RD Blends
RD Blends (French)
RD Blended with Biodiesel
RD Maximum Biodiesel Level
NPS Unit Name
CNG Station Sells Renewable Natural Gas
LNG Station Sells Renewable Natural Gas
Maximum Vehicle Class
EV Workplace Charging
Funding Sources
```

The model counts all available (`Status Code == "E"`) ports, including
private-access stations. It does not filter `Access Code` to public. Treating
these ports as competition for public charging is a limitation to discuss.
