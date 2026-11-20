# How human review changed the Michigan charging model

This case study comes from building the example used in the lesson. Read it
after your first $1 million result or failed attempt.

## Finding the data

The original search looked for population, EV registrations, and charging
stations by ZIP area. The team found Census population and internal
points, SEMCOG registrations, and AFDC charging stations. The agent also
collected county-level substitutes for missing ZIP-level tourism data. The
model left those out, so tourist and corridor traffic remains a gap.
[Data sources](../data/README.md)

## Reviewing the forecast

The first forecast projected 17,655 EVs into an area with 16,900 residents.
Two areas with corporate fleet registrations drove 61% of the modeled
revenue. The revised forecast caps EV counts at a share of the estimated
local vehicle fleet. A second check found that the two registration years
covered different ZIP areas. Comparing only areas present in both years
reduced the estimated growth rate from 51.7% to 40.2%.

## Reviewing the model

Gurobi returned `OPTIMAL` for all four versions. Each review asked whether
the model represented the business decision.

| Version | What the reviewer found | How the model changed |
|---|---|---|
| 1 | Fixed revenue per port sent 166 Level 2 ports to one ZIP area. | Tie revenue to customers served from a finite pool shared by both charging levels. |
| 2 | The plan projected $104.6 million in gross revenue on a $1 million budget. Assumed throughput and pricing implied $800,000 a year from one DC fast port, above the roughly $644,000 a 150 kW port could gross at $0.49/kWh running continuously. | Derive revenue and capacity from energy sold and revisit the demand forecast. |
| 3 | With uniform throughput, 183 ZIP areas could each absorb the full build at the same modeled revenue. | Estimate utilization by location and account for a fixed cost per opened site. |
| 4 | Utilization accounts for existing ports. Nearby new sites can still draw from the same customers. | Treat competition among new sites as a question to investigate before investing. |


Which of these checks would help you evaluate your own plan?
