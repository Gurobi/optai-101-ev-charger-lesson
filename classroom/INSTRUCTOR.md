# Run the one-hour lesson.

Two students share one coding agent. Assess how they check its work and
explain their decisions. The [student guide](README.md) is the handout. The
agent follows the [session guide](SESSION.md) in class and on screen.

## Before class.

1. Share the repository's clone URL and the
   [start prompt](../README.md#start-with-your-coding-agent). If you
   distribute a standalone copy, have students open it in the agent and use
   the prompt beginning with “Read AGENTS.md.”
2. Make sure students have access to a command-capable coding agent and
   [uv](https://docs.astral.sh/uv/getting-started/installation/). For live
   statewide solves, set up a free academic Gurobi license in the workspace
   where the agent runs Python. An academic WLS license can serve a remote
   workspace with access to the Gurobi token service. Keep the license
   outside the repo and credentials out of chat and shared screens.
   [Get a free academic Gurobi license](https://www.gurobi.com/academia/academic-program-and-licenses/).
3. Have students preflight with their agent.

   > Clone https://github.com/Gurobi/optai-101-ev-charger-lesson, read AGENTS.md, and run the classroom license
   > preflight. We will start the exercise in class.

   The agent runs `uv run --locked python lesson.py check --solver`.
   It tests a model above the bundled license's size limit. The check warns
   in the terminal and viewer if live solves are unavailable. Students can
   use saved plans during Test. Rerun the check after updating a license.
   uv supplies the pinned Python 3.14 if needed.
   In the workspace you'll use in class, start the viewer and open its URL
   before class. Local workspaces usually use `http://127.0.0.1:8765/`.
   Set up forwarding or host port publishing, or open the workspace's
   browser preview if needed. If you leave the viewer running, give the
   agent its URL with the start prompt so it can reuse that session.
4. Rehearse with students before teaching to check discussion timing.
   On your own machine, you can verify the archived plans and run the
   reference model with these commands.

   ```sh
   python3 lesson.py check
   uv run --locked python lesson.py reference
   uv run --locked python lesson.py reference --budget 500000
   ```

## Present the lesson live.

Use a fresh workspace and the [same start prompt as the students](../README.md#start-with-your-coding-agent).
Tell the agent you're presenting live. Preflight the workspace you'll use
on screen. Put the viewer beside the chat, and keep this guide and the
[case study](../journey/README.md) available off screen.

Choose **Start** and take the student’s role. Start from a choice the committee faces, such as where it might fund a pilot. Advance through the six tables in order. Point out one quantity you can read directly and another you would need to predict. Have the presenter use an `@agent` table note to ask for the comparison or definition they need. After the last table, read the reply on **Notes and replies**, then choose **Start forecasting**.

For example, a registration table counts vehicles by home ZIP. A station record can identify ports already installed there. Neither reports how often drivers use those ports. Think aloud about how a forecast error could reverse a choice between two proposed sites. Calculate an estimate for each candidate ZIP area during Forecast, then use those estimates as inputs to the site selection model during Formulate. Keep the historical figures off screen until the debrief.

## During class.

Use the [handout checkpoints](README.md#lesson-outline) to pace the room. Listen for a decision the pair can explain without the agent. These are good places to pause.

| When you hear or see this | What to do |
|---|---|
| “This ZIP has more EVs, so it needs more public chargers.” | Point to **Forecast → Method**. The registration count identifies a possible market. Have the pair distinguish the quantity they still need to forecast and explain how a different forecast could change the choice of site. |
| The pair accepts a model because the code runs. | Point to **Formulate → Trace**. Ask them to predict which plan the model should prefer or which constraint it should enforce. The agent can supply the test values and evaluate the formulation. |
| The team wants to move sites as soon as demand falls. | In **Test → Predict**, have them predict what happens at the sites they already chose. They can then price or score a redesign separately. |
| The first run fails. | Ask the agent to show the failed check. A hand calculation or a labeled saved plan can give the pair something to test in the time left. |

Leave ten minutes for the pitch. In the debrief, invite two pairs who would spend the money differently. Have each name one piece of evidence that could persuade them to adopt the other pair’s plan.

## Reference and fallback.

`python3 lesson.py sample` makes the saved $1 million plan available in
**Test → Predict** and **Test → Compare**.
`python3 lesson.py sample --budget 500000` adds the smaller budget after the
students record a prediction. Both commands work without Gurobi. Compare the
two saved scenarios with each other when using this route. If using a
student model, compare its own two runs with each other. The
[reference formulation](../model/FORMULATION.md) describes the archived model.

| Quantity | $1 million budget | $500,000 budget |
|---|---:|---:|
| Level 2 ports | 142 | 71 |
| DC fast ports | 0 | 0 |
| Capital spent | $996,000 | $498,000 |
| Discounted gross revenue | $3,615,683 | $1,827,435 |

The smaller budget's feasible set is contained in the original one, so its
mathematical maximum cannot rise. Locations can change and revenue can
fall by a different proportion than the budget. Compare solver gaps before
interpreting small differences between incumbents.

The reference model omits operating costs, corridor traffic, parcel and grid
feasibility, and competition among new sites. Seven of the 12 sites in the
$1 million plan are within five miles of another new site. Private-access
ports also affect the supplied utilization estimates. Ask what inputs or
constraints could change the all-Level-2 result.

If the agent is unavailable, discuss the [first model](../journey/README.md#reviewing-the-model).
It used fixed revenue per port and a budget constraint, then chose 166
Level 2 ports in one ZIP area. Ask students to explain how their model would
handle the next port.

## Assess the responses.

Collect one `student-responses.md` per pair from **Recommend → Submit**.
Score each row from 0 to 2.
Award 2 when the response includes both the work and the student’s interpretation described below. Award 1 for partial reasoning and 0 for a missing response or an unchecked assertion.

| Criterion | Evidence for full credit |
|---|---|
| Question and evidence | Explains what two sources measure, proposes a quantity to forecast, and shows how that estimate and one gap in the data could affect the recommended build or pilot. |
| Formulation and execution | Defines the objective, variables and constraints using the available data or stated assumptions. Checks the equations on a small case and reports a result from executing the model. |
| Stress test | Predicts the effect before the test and uses comparable numbers or a failed limit to explain what happened to the plan. |
| Recommendation | Tells the committee what to authorize, cites a test result, and answers an objection with evidence that could change the decision. |

Build, pilot, and defer can each earn 8/8. For a deferral, ask what to
measure, how to get it, and what finding would trigger investment. For a
build, ask what would prompt reconsideration. A documented failed solve can
earn full credit when the reasoning supports the proposed next step. Ask
each partner to explain one choice and one check in their own words.
