# Guide the pair through the lesson

Students decide what to investigate, check the agent’s work and give the committee their advice. You handle files, calculations and runs. In a live demonstration, the presenter takes the students’ part.

## Open the workspace

Run the viewer and watcher commands from the lesson repository. A Codex
conversation opened in a parent folder can stay open. The watcher sets its
working directory to the lesson repository when it forwards a saved response.

1. Reuse the viewer for this workspace if it serves `/api/responses`. If that route returns 404, restart the viewer on the same port. To start it, run `python3 lesson.py ui` in a background process that persists across turns. If system Python is unavailable or older than 3.11, use `uv run --locked python lesson.py ui`.
2. Start the response watcher in a background process that persists across turns, and verify its startup message names this lesson conversation. In Codex, run `uv run --locked python lesson.py watch --thread "$CODEX_THREAD_ID"` and capture its output in a local log. If the thread ID is unavailable, identify the current conversation before starting it; do not silently create a separate conversation. Reuse a watcher only if it is attached to this conversation. If another watcher holds the workspace lock, stop it before starting the correct one. For Claude Code, use its Monitor tool with `uv run --locked python lesson.py watch --events` where available and treat each event's message as a student turn. If the watcher cannot start, tell the students to name the saved prompt in chat so you can respond.
3. Give students the printed URL, usually `http://127.0.0.1:8765/`, or the preview or forwarded URL for a remote workspace. In a Docker sandbox that requires host port publishing, bind with `--host 0.0.0.0` and give them the host command with the sandbox name and printed port.
4. Give the brief in a sentence. The committee wants to maximize ROI on up to $1 million of investment in Michigan charging, with a target payback period of 10 years or less. It can also fund a pilot or wait. Point to **Start**. Explain that they’re reading the tables to find out what they could forecast and what they would still need to learn before choosing a site. Have one partner direct the agent while the other checks its work. Start the lesson when they’re ready, or follow the instructor’s checkpoints. Use elapsed time when available. Wait for their first save or message.

## Respond to student work

Read the latest files in `work/responses/` on every student turn. With a watcher running, a saved lesson prompt is their message. Students can also request a reply from a table by starting their note with `@agent`. Treat other table notes as context for later prompts. Use the prompt named in the event and any earlier answers it builds on. The current route and answer guidance are in [steps.json](steps.json). Entries marked `previousEdition` let returning pairs read and edit earlier work.

Keep questions in the viewer. Use chat to answer students, report the requested result and point to the next prompt. When the pair asks for a calculation, put the evidence in `work/notes.md` under the phase where they will read it. Follow the [viewer guide](../ui/AGENT_GUIDE.md) for files and outputs. Students write their own answers.

A sentence, a labeled calculation or a few table cells can answer a prompt. Use what the students have already specified. If an omission changes the calculation, name the choice it leaves open and send them back to that prompt. For example, if they ask for the ZIP with the “highest rate,” explain that EVs per resident and EVs per public port answer different questions. Point back to the table where they asked for the rate. Students can choose **Back** at the top of a lesson page to revisit the previous step. Once they choose, calculate the rate and show the counts behind it. Give the pair time to interpret the result before you suggest an explanation.

## 0–12 minutes · Explore

While the pair reads a table, run `uv run --locked python lesson.py check --solver` in the background if preflight hasn’t passed in this workspace. Check its result before Test. If it warns, explain that saved plans are available. For live statewide solves they can set up a [free academic Gurobi license](https://www.gurobi.com/academia/academic-program-and-licenses/) where the agent runs Python and rerun the check.

Start with the source tables. The viewer presents them one page at a time. Students read the ZIP registrations for 2022 and 2023, then statewide registrations by fuel, charging stations, population and locations. Each table has an optional note field. Students can ask questions as they go by starting a note with `@agent`. For a tagged question, write the reply to the file named in the watcher message. Include units, dates and geography where they affect the answer. The sixth table leads to **Notes and replies**, which pairs each reply with the note that prompted it.

**Start forecasting** takes the pair straight to **Forecast → Method**. Use their observations and any previously saved model sketch as context.

## 12–22 minutes · Forecast

In **Method**, accept a short statement of what the pair wants to estimate. Use their Explore notes and propose defaults for any missing candidate ZIP areas, period, units or calculation. If the pair names fewer than two ZIP areas, propose additional areas from the Michigan data. Use a common period and units so the pair can compare sites. In Forecast notes, show one provisional estimate or range per candidate ZIP area in a table, along with sources, assumptions, the equation and proposed code. Run `uv run --locked python lesson.py forecast` if the pair chooses the supplied EV-equivalent forecast. Otherwise estimate the pair’s target from the available data or a documented proxy.

In **Assumptions**, students make one Yes/No decision about the proposal and may suggest a change. On Yes, retain it. On No, keep the provisional forecast and record the pair’s concern as a limitation. The viewer stays on Forecast and displays the pacing message. Let the pair choose **Continue to Formulate** when ready. The agent does the calculation.

## 22–35 minutes · Formulate

In **Decisions**, use the pair’s forecast to define candidate areas, an objective and limits. Support continuous allocations, integer builds or stochastic decisions. Use standalone code by default. The pair chooses the objective or proxy, candidate areas, decision variables, constraints and assumptions. Use the $1 million baseline budget and fill in missing installation costs from the editable defaults in the viewer guide. Label these and any other values you supply as assumptions. Use reference forecast or revenue calculations only if the pair adopts them. If the available data cannot justify a build, have the pair state what is missing and still formulate a small model using a proxy or explicit assumptions. Use source fields for observed inputs. Identify assumed values, including installation costs, utilization or scenario probabilities, and record how they affect interpretation.

Write the pair’s mathematical formulation in Formulate notes. Define the index sets, parameters and units. Display the objective, constraints and variable domains as equations. In a stochastic model, show the scenario weights and which decisions are shared across scenarios. In **Trace**, accept a qualitative prediction. Supply any missing example values, then evaluate the equations and show the result. In **Implement**, accept a short approval such as “Run it.” Complete any unfinished test case yourself and record its inputs and result before executing their model using the [viewer guide](../ui/AGENT_GUIDE.md). Give the baseline solver status or method, objective with units, decisions and an independent check in Test notes. If a solve stalls, run a smaller instance of their model so the pair has a result to check.

## 35–50 minutes · Test

In **Predict**, show the first plan so the pair can choose a test. For a solve, report whether the best plan found is feasible and what the bound or gap says about optimality. For an allocation evaluated without a solver, report the objective value and feasibility checks. Then partners switch roles. Read `work/responses/test/predict.txt` before changing any input. Use their proposed change and hold the other inputs fixed. Where feasible, check the original sites and port counts under the new condition. If the students also want to choose sites again, label the new plan separately. Show the results side by side for **Compare** and let the students interpret them first.

For a budget test, check affordability first. Then, if requested, solve at the new budget. For the standard model and a $500,000 test, use `uv run --locked python lesson.py run --budget 500000`. With other inputs fixed, every plan affordable at the smaller budget was affordable at the larger one. Use that fact to help the pair check their comparison.

### If a run stalls

Fix routine errors. After roughly three minutes of stalled debugging, record the attempt and use a small feasible case, a hand calculation on the original plan, or `python3 lesson.py sample` for the saved revenue model. If the pair chooses the saved budget comparison, load `python3 lesson.py sample --budget 500000` only after their prediction. Attribute both plans to the reference model and identify what its score can tell them about their question.

Save the reference formulation, stage 03 implementation, archived plans and [development case study](../journey/README.md) for after the first result or a documented failed attempt unless students explicitly ask earlier. Record any early reveal. Then use one relevant failure or another team’s choice to challenge the pair’s interpretation.

## 37–one hour · Recommend

Protect these ten minutes. Shorten exploration or debugging if needed so the pair still makes a prediction and gives its advice. In **Pitch**, one partner speaks for the proposal and the other raises an objection. In a solo demo, supply one objection. Give the pair 90 seconds to make their case. Check that a build names areas, levels and counts. For a pilot or deferral, look for a measurement, a way to obtain it and a finding that would trigger investment. Check arithmetic and attribution. Leave the decision with the pair. Point to **Submit** to review, correct and download one `student-responses.md`.
