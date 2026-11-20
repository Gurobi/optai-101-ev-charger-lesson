"""Calibrated assumptions this pipeline fills in that the raw data can't answer.

The inputs below mix observations from `data/`, estimates informed by public
sources, and teaching assumptions. Costs, distance scales, growth limits, and
other judgment calls require review; a citation does not make them measured
Michigan values. Derived parameters preserve the energy/revenue identity,
while the inputs still need evidence and sensitivity analysis.

Derivation chain
----------------
Everything hangs off two physical quantities:

    q   = annual PUBLIC charging energy demanded by one EV        (kWh/EV/yr)
    E_l = annual energy one level-l charger actually dispenses    (kWh/port/yr)

from which the two model parameters follow:

    throughput  k_l = E_l / q          (EVs one charger can serve per year)
    revenue     p_l = q * price_l      ($/yr per EV served)

so that revenue per charger per year, k_l * p_l, reduces to E_l * price_l:
energy sold times the price of energy. That identity is what keeps the model
physically honest, and it is what v2 violated.

v4 adds one more layer. E_l above is the *statewide average* a port
realizes. A port's actual throughput depends on how many EVs are nearby
competing for how many existing ports, so v4 computes a utilization factor
u in (0, 1) per ZCTA and level from the geography (see 02_forecast_demand.py)
and lets a port realize up to PEAK_THROUGHPUT_MULTIPLE times the average:

    k_{z,l} = PEAK_THROUGHPUT_MULTIPLE * E_l * u_{z,l} / q

calibrated so that the average existing Michigan port realizes exactly E_l.
That is what makes location matter: v3 had the same k everywhere and 183
ZCTAs tied for optimal.
"""

# Charger levels considered (Level 2 AC, Level 3 / DC fast).
LEVELS = (2, 3)

# Total capital budget, from the natural-language prompt.
BUDGET = 1_000_000.0


# --------------------------------------------------------------------------
# Vehicle-side inputs -> q, the public charging energy one EV demands per year
# --------------------------------------------------------------------------

# Annual miles per EV. US light-duty average is roughly 13,500 mi/yr; EVs
# are driven somewhat less than the fleet average, so this sits below it.
ANNUAL_MILES_PER_EV = 11_000.0

# Real-world consumption including charging losses. Typical modern EVs run
# 0.26-0.40 kWh/mi; 28 kWh/100mi (0.28) is the commonly cited average, and
# 0.30 allows for Michigan winters.
KWH_PER_MILE = 0.30

# Share of an EV's annual charging energy taken on public infrastructure
# rather than at home. NREL's 2030 charging projection puts 64% of charging
# at single-family homes, leaving ~36% across public/workplace L2 and DC
# fast. Source: NREL, "The 2030 National Charging Network" (NREL/TP-5400-85654).
PUBLIC_CHARGING_SHARE = 0.36

# PHEVs charge publicly far less than BEVs (small battery, mostly home
# charging), but they are not zero. They are counted as this fraction of a
# BEV when converting Michigan's registration totals into "EV equivalents."
PHEV_PUBLIC_CHARGING_EQUIVALENT = 0.4

# Derived: kWh of public charging demanded by one EV per year.
ANNUAL_PUBLIC_KWH_PER_EV = ANNUAL_MILES_PER_EV * KWH_PER_MILE * PUBLIC_CHARGING_SHARE


# --------------------------------------------------------------------------
# Charger-side inputs -> E_l, the energy one charger actually dispenses
# --------------------------------------------------------------------------

# Measured throughput, not nameplate capacity. This is the number v2 got
# wrong by roughly 40-90x, so it is worth being explicit about the evidence.
#
# Level 2: NREL measured US public L2 ports at 5.83 kWh/port/day (retail,
#   weekday) to 10.6 kWh/port/day (leisure destinations, weekend) in 2022.
#   Source: NREL, "Evaluating Electric Vehicle Public Charging Utilization"
#   (NREL/TP-5400-85902). US EVs per public port has roughly doubled since
#   that data was collected, so a well-sited paid port today is placed just
#   above the top of the 2022 measured range.
#
# Level 3: Paren's 2025 industry data puts corridor DC fast ports at
#   176 kWh/port/day with national network utilization at 16.4%. Corridor
#   sites are the busiest in the country, so a general-purpose site is set
#   below that figure.
#
# For reference, nameplate 24/7 capacity is 264 kWh/day for an 11 kW L2 and
# 3,600 kWh/day for a 150 kW DC fast unit. Real ports run at a few percent
# of that, which is exactly why utilization cannot be waved away.
KWH_PER_CHARGER_PER_DAY = {2: 11.0, 3: 150.0}

ANNUAL_KWH_PER_CHARGER = {
    level: kwh_per_day * 365.0 for level, kwh_per_day in KWH_PER_CHARGER_PER_DAY.items()
}


# --------------------------------------------------------------------------
# Price -> measured from our own AFDC data, not assumed
# --------------------------------------------------------------------------

# Median $/kWh across Michigan stations that publish a per-kWh price in the
# `EV Pricing` column of data/michigan_ev_charger_locations. Only 9%
# of Michigan stations disclose pricing, and 84% of the L2 stations that do
# are free (hotel, workplace, and municipal amenity charging), so these
# medians describe the *paid* segment a revenue-seeking operator competes in:
#   L2   n=12  min 0.14  median 0.39  max 0.60
#   DCFC n=7   min 0.41  median 0.49  max 0.50
# Small samples. They agree with national averages, which is why they're used.
PRICE_PER_KWH = {2: 0.39, 3: 0.49}


# --------------------------------------------------------------------------
# The two parameters the model actually consumes
# --------------------------------------------------------------------------

# k_l: how many EVs' worth of annual public charging one charger can serve.
THROUGHPUT_PER_CHARGER = {
    level: ANNUAL_KWH_PER_CHARGER[level] / ANNUAL_PUBLIC_KWH_PER_EV for level in LEVELS
}

# p_l: annual revenue from one EV served at this level.
ANNUAL_REVENUE_PER_EV = {
    level: ANNUAL_PUBLIC_KWH_PER_EV * PRICE_PER_KWH[level] for level in LEVELS
}


# --------------------------------------------------------------------------
# Capital cost: per-site fixed + per-port
# --------------------------------------------------------------------------

# Installed cost has two parts. The per-site part is the utility service
# upgrade, transformer, trenching, permitting, and interconnection: paid
# once per location however many ports go in. The per-port part is the
# charger hardware and its pedestal. Make-ready civil and electrical work
# is 50-70% of a typical bill, which is why the fixed part is large.
#
# 2025-26 commercial ranges are $7,000-$15,000 per installed L2 port and
# $90,000-$150,000 per installed 150 kW DC fast port, all-in. The split
# below lands inside those ranges at realistic site sizes: a 6-port L2 site
# costs $8,000/port and a 2-port site $12,000/port; a 4-port DC fast site
# costs $117,500/port and a 2-port site $155,000/port.
#
# v2 used $6,000 and $60,000 per port, both below the bottom of the current
# ranges. v3 used all-in per-port midpoints ($10,000 and $115,000) with no
# fixed part, which made the cost of a site linear in its port count and
# let the solver treat one 8-port site and four 2-port sites as identical.
SITE_FIXED_COST = {2: 12_000.0, 3: 150_000.0}
PORT_COST = {2: 6_000.0, 3: 80_000.0}

# Sites are built in pairs at minimum (industry practice, and a single port
# is a poor customer experience). Upper bounds keep one location from
# absorbing a whole budget: a 12-port L2 lot or an 8-port DC fast plaza is
# a large site in Michigan today.
MIN_PORTS_PER_SITE = {2: 2, 3: 2}
MAX_PORTS_PER_SITE = {2: 12, 3: 8}


# --------------------------------------------------------------------------
# Location-dependent utilization (v4)
# --------------------------------------------------------------------------

# How far a driver will go to a charger of each level, as the distance at
# which a ZCTA's EVs count 1/e as much toward a site's catchment. L2 is
# neighborhood charging (you plug in where you already are); DC fast draws
# from a wider area because the stop is the point of the trip.
CATCHMENT_DECAY_MILES = {2: 3.0, 3: 12.0}

# The busiest a new port can be, as a multiple of the statewide measured
# average (KWH_PER_CHARGER_PER_DAY). NREL's 2022 L2 measurements ran from
# 5.83 to 10.6 kWh/port/day across site types, so the best individual sites
# sit several times above the mean. 2.5x is a judgment call: high enough to
# separate good sites from poor ones, low enough that a fully utilized DC
# fast port (375 kWh/day) is still at about 10% of its 3,600 kWh nameplate.
PEAK_THROUGHPUT_MULTIPLE = 2.5

# k_l ceiling: EVs one port can serve per year when fully utilized.
PEAK_THROUGHPUT_PER_CHARGER = {
    level: PEAK_THROUGHPUT_MULTIPLE * THROUGHPUT_PER_CHARGER[level] for level in LEVELS
}


# --------------------------------------------------------------------------
# Time value of money
# --------------------------------------------------------------------------

# Charger economic service life. Also caps how far the EV adoption forecast
# is projected.
SERVICE_LIFE_YEARS = 10

# Discount rate applied to future revenue.
DISCOUNT_RATE = 0.08

# Ordinary annuity factor: the present value of $1/year for the service
# life. This replaces the flat `SERVICE_LIFE_YEARS` multiplier that v2 used
# in the objective, which valued year-10 dollars the same as year-1 dollars.
# At 8% over 10 years it is 6.710, not 10.
LIFETIME_REVENUE_FACTOR = sum(
    1.0 / (1.0 + DISCOUNT_RATE) ** year for year in range(1, SERVICE_LIFE_YEARS + 1)
)


# --------------------------------------------------------------------------
# EV adoption forecast
# --------------------------------------------------------------------------

# The empirical statewide growth rate is computed from the SEMCOG 2022 and
# 2023 registration files at runtime (see 02_forecast_demand.py) rather than
# hardcoded, but it is only applied for the first few years. Extrapolating an
# early-adoption growth rate across a full 10-year horizon is what produced
# v2's forecast of more EVs than residents in some ZCTAs.
EV_GROWTH_YEARS_AT_EMPIRICAL_RATE = 3
LONG_RUN_ANNUAL_EV_GROWTH_RATE = 0.05

# Ceiling on how many EVs a ZCTA can plausibly hold, as a share of its own
# light-duty vehicle fleet. Vehicles per resident is computed from the AFDC
# statewide registration totals (~0.87 for Michigan). 27% is an aggressive
# but physically reachable EV share for the state's most EV-forward ZCTA a
# decade out.
#
# Without this ceiling, uniform compound growth applied to ZCTAs whose
# registration counts are inflated by fleet/corporate registrations produces
# impossible demand. 48033 (Southfield) and 48359 (Lake Orion, home of GM's
# Orion Assembly plant) report 95 and 69 EVs per 1,000 residents against a
# statewide 4.4, and in v2 those two ZCTAs alone drove 61% of the objective.
MAX_EV_SHARE_OF_VEHICLE_FLEET = 0.27
