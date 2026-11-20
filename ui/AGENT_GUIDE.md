# Put the student's work in the viewer.

The viewer saves student answers to `work/responses/<phase>/<prompt>.txt`.
Read these files when the student messages you. Students own those answers
and download them from **Recommend → Submit**. Put your evidence in
`work/notes.md`. Follow the [session guide](../classroom/SESSION.md) for
when to show each piece of evidence.

| Tab | Write in `work/notes.md` | Shown from other files |
|---|---|---|
| Explore | Answers to any data questions, in order, with their sources | Six tables, then Notes and replies, which shows the saved notes and tagged replies together. Its button opens Forecast. |
| Forecast | Concise estimate, sources, assumptions, equation, proposed code, and the final revision | EV-equivalent map in Assumptions when using the supplied forecast |
| Formulate | The agreed equations, variable domains, units, and a traced example | Parameters and implemented model in Implement |
| Test | Checks, results, and any failed attempts | Run summary, logs and selected sites in Predict, and runs side by side in Compare. Saved reference plans appear when explicitly loaded. |
| Recommend | Calculations or evidence the student requests | The submission assembles the student's saved answers |

Use the headings in [the notes template](../classroom/notes.md). Older
workspaces can keep their existing headings. The viewer groups “Run the
model” and “Read the solver log” under Test, and “Read the plan” under
Recommend. Keep your evidence concise and attribute any quotations from the
students. Plain paragraphs, lists, Markdown
tables, inline emphasis, and code blocks render in the browser. In Formulate,
use a fenced `math` block with Unicode symbols or plain mathematical notation
for the objective, constraints, and domains. Define the symbols in the
surrounding notes. For example, for integer port counts `xᵢ` and per-port
benefits `rᵢ`, an objective line could read `maximize  ∑ᵢ rᵢ xᵢ`.

## Charts.

Use a table or summary when that answers the question. For a plot, let the student choose what to show. Use one of these fenced chart
formats in the notes. For bar, line, and map charts, enter one `label, value`
pair per line. For scatter plots, enter `label, x, y`.

| Fence | Title and data |
|---|---|
| `bars` | Add the title after the fence. Enter up to 30 labeled values in the order you want them displayed. |
| `line` | Add the title after the fence. Enter the points in order. |
| `map` | Add the title after the fence. Use a five-digit ZIP area code for each label. |
| `scatter` | Add a title and axis names in the form `Title \| x name vs y name`. |

````
```bars EVs registered in 2023 by ZIP area
48103, 1312
48105, 890
```
````

For custom figures, use Matplotlib, Seaborn, Plotly, or another plotting
library. Export PNG or SVG for a static figure, or write a self-contained
Plotly HTML file for hover, zoom, and map controls. Save the file in
`work/figures/` and put its reference on its own line in `work/notes.md`.

```markdown
![Available charging stations by ZIP area](figures/charger-map.png)
![Interactive map of available chargers](figures/charger-map.html)
```

File names may use letters, digits, hyphens, and underscores. Put the
renderer in the Plotly export and let the figure size itself in the viewer.

```python
fig.write_html(
    "work/figures/charger-map.html",
    include_plotlyjs=True,
    config={"responsive": True},
)
```

The lesson displays HTML figures as read-only previews in isolated frames. Use a static chart when possible. The figure file in the workspace retains its interactive controls. HTTPS basemaps and
map data can load from services that allow requests from that frame.
Maps using WebGL need browser support. Use embedded geometry or a static
export for offline use.
Keep plot code in `work/` when students need to reproduce it. Name the data
source, geographic unit or coordinates, and filters in the caption or notes.

## Forecasts and model runs.

Show a student-defined forecast as a table or figure in Forecast notes.
Include the target, units, geography, horizon, method and provisional estimate. Ask up to three numbered yes-or-no questions about specific assumptions in Forecast notes.
The optional EV map reads the supplied EV-equivalent forecast in
`work/demand.csv`. Standalone models can store their inputs in any workspace file format.

### Run the pair’s own model.

Use a standalone model by default. Implement the pair’s agreed equations in
a script under `work/`. The supplied data and investment brief define the
exercise. The pair chooses candidate areas, decision variables, objective or
proxy, constraints, assumptions, and solver.

Use the $1 million baseline budget from the brief. If the pair models
installation costs and gives no values, use the editable defaults seeded in
`work/parameters.json`. A Level 2 installation costs $12,000 to open plus
$6,000 per port. A DC fast installation costs $150,000 to open plus $80,000
per port. Apply the opening charge once per modeled area and charger type
unless the pair defines a different site structure. Use the pair’s values
where provided, and label any defaults as assumptions in Formulate notes.
For a missing model-specific input, derive a value from the data where
possible or state an assumption that fits the model. The remaining
reference parameters apply when the pair adopts the reference assumptions. For a standalone
Python model saved as `work/solve.py`, run it from the repository root with
`uv run --locked python work/solve.py`. The agent can run other workspace code
with its applicable CLI. Use the observed Michigan data, the pair’s forecast
or a documented proxy, and explicit assumptions. Keep the model code and its
inputs in the workspace so the pair can reproduce the run. For an LP, state
what a fractional decision represents and how it informs the recommendation.
For a stochastic model, document the scenario values, probability weights
and when each decision is made.

In Test notes, record the command, inputs or scenario, solve status, objective
and units, the resulting decisions and an independent check. Where available,
report the bound or gap for a stopped solve with an incumbent. The viewer
shows these notes in Predict and Compare. To stress-test a standalone model,
first fix the baseline decisions that were made before uncertainty resolves.
Change the chosen input and reevaluate feasibility and score, allowing only
the recourse defined by the formulation. Report a newly optimized plan
separately if the pair requests one.

### Use the structured runners when their output fits.

If the pair explicitly chooses the supplied EV-equivalent and discounted
gross revenue assumptions, use
`uv run --locked python lesson.py forecast`, implement the agreed formulation
in `work/model.py` using its return contract, then use
`uv run --locked python lesson.py run`. The runner checks budget, integer
counts, site limits, capacity, pooled local demand, and revenue arithmetic.
Add a check for any further condition the students choose.

If the pair wants the viewer’s structured results for an integer-port
allocation with per-area/type opening and per-port costs, use
`uv run --locked python lesson.py evaluate --scenario "Initial shortlist"`.
The command checks feasibility and computes the objective value for the proposed allocation.
Prepare the following in `work/` after agreeing on the model.

- In `candidates.csv`, provide one row per candidate with a five-digit
  `zcta` and the columns the students chose. Keep forecast construction code
  in the workspace so the estimate can be reproduced.
- In `parameters.json`, set `SITE_FIXED_COST` and `PORT_COST` in dollars
  with level keys `"2"` and `"3"`. Use the editable installation cost defaults for any values the pair leaves open.
  Add the team's other scenario inputs here or in the candidate table.
- In self-contained `analysis.py`, set `METRIC` and `UNIT` to descriptive
  strings. Implement `propose(candidates, parameters, budget)` returning a
  list of dictionaries with `zcta`, `level` (2 or 3), and positive integer
  `count`. An empty list represents no build. CSV input cells are strings.
- Implement `check_and_score(sites, candidates, parameters, budget)` in the
  same file. Check at least one consequential model-specific condition and
  raise a descriptive exception on violation. Recompute the metric from
  the supplied allocation and inputs and return a finite number. Each
  installed site has `zcta`, integer `level`, integer `count`, and computed
  `capital`. The runner separately checks candidate membership, unique
  area/level pairs, counts, and budget. A checked score makes no optimality claim.

Each attempt snapshots its inputs and writes a run record to `work/runs/`.
For a fixed-build stress test, change the chosen scenario input, then run
`uv run --locked python lesson.py evaluate --scenario "Lower demand, original build" --plan work/runs/<baseline>/solution.csv`.
Use the actual baseline directory. The evaluator skips proposal generation
and checks the original counts at the new inputs. A budget violation or failed
model-specific check is evidence of infeasibility. Record which check failed.
Omit `--plan` for a new allocation and give that scenario a distinct name.
A plan from the standard runner can also be evaluated this way if its areas
appear in the candidate table. For a simple hand calculation, record the
inputs, arithmetic, units, and result directly in Test notes.
