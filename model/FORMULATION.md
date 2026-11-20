# Current EV charging model.

This is the reference model for the lesson. The
[case study](../journey/README.md#reviewing-the-model) explains how human
review changed the earlier versions.

## Natural-language prompt.

Optimize EV charger placement in the State of Michigan. I've got $1 million
budget, am okay with either Level 2 or Level 3 chargers. Where should I put
them to maximize revenue over the life of the charger? Level of granularity
is ZCTA. I want the answer in terms of [zcta, level, count].

## Sets and inputs.

- Z: 992 Michigan working ZCTAs, indexed by z.
- L = {2, 3}: Level 2 AC and DC fast charging, indexed by l.
- B: capital budget, $1,000,000 by default; scenarios change this value.
- f[l], c[l]: fixed site cost and per-port capital cost in dollars.
- m[l], M[l]: minimum and maximum ports per opened site.
- d[z]: projected EV-equivalent demand, discount-weighted over ten years.
- u[z,l]: dimensionless utilization, precomputed from EVs and existing ports.
- k[z,l]: annual EV-equivalent service capacity per new port at that location.
- p[l]: annual gross revenue per EV-equivalent served.
- A: ten-year annuity factor at an 8% discount rate, approximately 6.710.

## Decisions.

- y[z,l] in {0,1}: open a site of charging level l in ZCTA z.
- x[z,l] nonnegative integer: number of ports installed there.
- s[z,l] nonnegative continuous: annual EV-equivalent demand served.

An opened site is one modeled site of a given level within a ZCTA, rather
than a selected street address or parcel. Both levels can be opened in the
same ZCTA, each paying its own fixed cost.

## Objective and constraints.

Maximize discounted gross revenue:

$$\max \sum_{z\in Z}\sum_{l\in L} A p_l s_{z,l}.$$

Realized port capacity:

$$s_{z,l} \le k_{z,l}x_{z,l} \quad \forall z,l.$$

Site-opening logic and port limits:

$$m_l y_{z,l} \le x_{z,l} \le M_l y_{z,l} \quad \forall z,l.$$

Shared demand across charging levels within each ZCTA:

$$\sum_{l\in L}s_{z,l} \le d_z \quad \forall z.$$

Capital budget:

$$\sum_{z\in Z}\sum_{l\in L}(f_l y_{z,l}+c_l x_{z,l}) \le B.$$

These constraints plus the domains above form a mixed integer linear model.
The objective excludes capital subtraction and operating costs. Capital
limits feasibility, while the objective measures gross revenue. Spending
nothing is feasible. No minimum coverage or equity condition is imposed.

## Parameter construction.

Annual public-charging demand per EV-equivalent is
q = 11,000 miles * 0.30 kWh/mile * 0.36 = 1,188 kWh/year.
Let E[l] be average annual energy dispensed per port and mu = 2.5. Then:

$$p_l = q\pi_l, \qquad k_{z,l}=\mu E_l u_{z,l}/q.$$

Revenue per fully used modeled port is therefore mu * E[l] * u[z,l] *
price[l]. This identity ties service capacity and revenue to energy sold.

| Input | Level 2 | DC fast | Basis |
|---|---:|---:|---|
| Average energy dispensed | 11 kWh/day | 150 kWh/day | Teaching estimates informed by measured US throughput |
| Price | $0.39/kWh | $0.49/kWh | Paid-price medians from the archived AFDC pricing field |
| Fixed site cost | $12,000 | $150,000 | Assumed split of installation costs |
| Per-port cost | $6,000 | $80,000 | Assumed split of installation costs |
| Minimum / maximum ports | 2 / 12 | 2 / 8 | Teaching assumptions |
| Catchment distance scale | 3 miles | 12 miles | Teaching assumptions |

`constants.py` contains all numerical assumptions and the original evidence
notes. NREL reports TP-5400-85654 and TP-5400-85902 inform charging-share and
throughput assumptions. The DC throughput note cites a published Paren
industry figure, not a redistributed proprietary dataset. The assumed
cost split and distance scales have not been fitted to observed Michigan
site economics. Price samples are small (12 paid Level 2 stations and
7 DC fast stations); they describe the reporting paid segment.

Stage 01 joins 2023 ACS population, 2022/2023 SEMCOG registrations, the
2026-08-17 AFDC station snapshot, and 2023 Census internal points. It
rescales the retained 2023 registration distribution to 2025 statewide
BEVs plus 0.4 times PHEVs. ZIP/ZCTA code matching, zero-filling unreported
counts, and retaining an older spatial distribution are explicit shortcuts.

Stage 02 grows registrations using the positive-count overlap of 2022
and 2023 for three years, then 5% yearly. Each year's demand is capped
at 27% of a ZCTA's estimated vehicle fleet. Discount weighting reduces
the ten annual projections to one demand parameter d[z]. This is a
single-period approximation, rather than annual capacity allocation.

Using great-circle distances delta between internal points, set
`w[l](delta) = exp(-delta / lambda[l])`. For each ZCTA and level:

$$N_{z,l}=\sum_j w_l(\delta_{zj})d_j,\quad
P_{z,l}=\sum_j w_l(\delta_{zj})e_{j,l},\quad
\rho_{z,l}=N_{z,l}/(P_{z,l}+1),$$

$$u_{z,l}=1-\exp(-\rho_{z,l}/\rho^0_l).$$

Here e[j,l] counts available existing ports, including private-access
stations. The saturation scale rho0[l] is calibrated so the existing-port-
weighted mean utilization is 1/mu = 0.4. This calibration enforces a chosen
average; it is not independent validation of site demand. Competition is
fixed before solving, so the model stays linear.

## Choices requiring human review.

- New sites do not compete with other new sites across ZCTA boundaries.
  Adding nearby sites can overstate the demand available to each.
- Local shared demand and regional utilization use different geographic
  scopes. Demand is not explicitly allocated along origin-destination flows.
- Residence/fleet registrations omit corridor traffic and tourism. A
  zero-resident airport ZCTA gets a zero fleet-based demand ceiling.
- Supply includes available private-access stations. Public availability
  and charging behavior may differ from what their port counts suggest.
- Straight-line distances between internal points approximate access;
  parcel feasibility, grid capacity, land availability, and actual road
  travel are absent.
- The model omits electricity, demand charges, maintenance, rent, financing,
  and a profit objective. It also treats Level 2 and DC fast demand as
  substitutes within a ZCTA.
- Growth, fleet ceiling, PHEV weight, price, utilization, and costs all need
  sensitivity analysis before using a recommendation commercially.

The frozen baseline chooses 142 Level 2 ports across 12 ZCTAs, spends
$996,000, and earns about $3,615,683 modeled revenue NPV. This result is
conditional on the inputs above. Gurobi's optimal status uses its numerical
and MIP-gap tolerances; it does not certify these real-world assumptions.
