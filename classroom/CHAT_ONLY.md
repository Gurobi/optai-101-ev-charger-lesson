# Michigan EV charging in chat

Copy the starter prompt into any web-connected chatbot. Keep a shared
document for your answers. One partner directs the chat and the other
checks the evidence. Switch roles before the budget test.

## Starter prompt

```text
Guide our pair through this Michigan EV charging lesson one phase at a time.
Wait for our answer before advancing. We can paste text and check arithmetic.
Use the data below. Ask us for any missing evidence and label assumptions.

Brief
We advise a company with up to $1 million for Level 2 or DC fast charging
in Michigan. It wants a return on the investment and a payback period of
10 years or less. We can recommend a build, a pilot, or waiting.

Michigan evidence
ZCTA  | Population | 2022 EVs | 2023 EVs | Existing L2 ports | Existing DC fast ports
48104 | 43,762     | 395      | 533      | 118               | 3
48105 | 36,959     | 489      | 682      | 46                | 6
48201 | 14,327     | 49       | 58       | 115               | 4

The course joined SEMCOG ZIP registration counts to Census ZCTAs. Population
is the 2019–2023 ACS estimate. Ports are available ports from the 2026 AFDC
snapshot and include private access. These measurements are from different
years. Registrations and port counts are proxies for demand and supply.
Source is the course archive model/reference/zcta_features.csv.
Copyright © 2019 SEMCOG. All Rights Reserved. Reproduction or Use Without Permission is Prohibited.

1. Explore. Ask us for one comparison across areas and one gap that could
   change a site decision. Check units and years with us.
2. Forecast. Ask us to choose at least two ZIP areas, a future quantity
   and a shared time horizon. Work out an estimate for each area and show
   them together in a table with common units. Keep the observed counts
   and assumptions explicit, then ask us to approve or revise the assumptions.
3. Formulate. Ask us to choose two candidate areas, a charger type, a fixed
   number of ports per site, costs and a measurable objective or proxy.
   If we need numbers, suggest clearly labeled teaching assumptions that
   make the budget matter. Write binary build decisions, a budget constraint
   and an objective with units. List the four build choices, check costs
   and scores with us, and select the best affordable choice by hand.
4. Test. Show our baseline choice and ask us to predict what happens if
   the budget falls to $500,000. Wait for that prediction, then check the
   same four choices with the new cap. Ask us to paste the saved statewide
   results from the worksheet. Use them as evidence about the course's
   reference model, keeping their assumptions distinct from our model's.
5. Recommend. Ask us for a 90-second build, pilot, or wait recommendation
   and one objection from our partner. A build names areas, types and port
   counts. A pilot or wait names a measurement, how to collect it, and a
   threshold for building. Help us check whether the evidence supports a
   claim about ROI or payback.

Help us assemble one Markdown hand-in with our observations, forecast and
assumptions, equations and baseline result, prediction and test result,
and recommendation with its supporting evidence. Use our own reasoning.
```

## Saved results for Test

Paste this table and the paragraph beneath it into the chat after your pair
records its budget prediction and checks its two-site model.

| Statewide cap | Capital spent | Sites | Level 2 ports | Ten-year discounted gross revenue |
|---:|---:|---:|---:|---:|
| $1,000,000 | $996,000 | 12 | 142 | $3,615,683 |
| $500,000 | $498,000 | 6 | 71 | $1,827,435 |

The course reference model reoptimized under each cap. Its objective is
gross revenue discounted at 8%, with operating costs excluded. Assessing
ROI or payback would also require cash-flow timing and operating costs.
Sources are the [baseline plan](../model/reference/README.md) and the
[half-budget plan](../model/half_budget/README.md).
