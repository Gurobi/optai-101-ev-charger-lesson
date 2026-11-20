# Plan EV charging in Michigan.

A company has up to $1 million to invest in Level 2 or DC fast charging. Where in Michigan should it build? Would a pilot, or a decision to wait, be a better use of the money?

Two students share a coding agent for one hour. The pair reads Michigan’s EV records and chooses a quantity to forecast before deciding where to add ports. They review the forecast assumptions and write a model for the investment decision. Before the agent tests the plan, the students
predict what will happen if one of their assumptions changes. They finish
with a 90-second recommendation to the investment committee.

## Start with your coding agent.

Before class, students need access to a coding agent that can run terminal
commands and [uv](https://docs.astral.sh/uv/getting-started/installation/). The lesson
can use saved plans during Test when live solves are unavailable.

For live statewide solves, set up a free academic Gurobi license where the
agent runs Python. The statewide model exceeds the size limit of the
license bundled with `gurobipy`.
[Get a free academic Gurobi license](https://www.gurobi.com/academia/academic-program-and-licenses/).

1. Copy this repository's clone URL or use the URL your instructor gave you.
   Paste the following into your coding agent and replace `<repo URL>`.

   > Clone <repo URL>, read AGENTS.md, and guide us through the one-hour
   > Michigan EV charging lesson. Start the viewer and give us the browser URL.

2. Open the URL the agent gives you, usually `http://127.0.0.1:8765/`. Put
   the browser on one side of your screen and the agent's chat on the other.
   Read the course overview, then choose **Start**. One student
   drives the chat and the other checks the evidence. Switch roles before
   running your chosen stress test.
3. Follow the blue button through the six tables. Ask questions as you go by starting a table note with `@agent`. Read your notes and replies on **Notes and replies**, then choose **Start forecasting**.
   If the agent doesn’t reply automatically, tell it which prompt you saved.
   It reads your saved answers from the workspace. At **Recommend → Submit**,
   download one `student-responses.md` per pair.

If the repo is already open in the agent, start the prompt at “Read AGENTS.md.”
The [student guide](classroom/README.md) has the checkpoints and hand-in details.

### Watch for saved answers.

The agent starts the watcher when the lesson begins. With the Codex App
Server running, it attaches the watcher to the current lesson conversation:

```sh
uv run --locked python lesson.py watch --thread "$CODEX_THREAD_ID"
```

If the thread ID is unavailable, identify the lesson conversation and supply its ID. Saving a lesson prompt starts a turn in Codex. Table notes start a turn only when the student begins the note with `@agent` and includes a request. The viewer shows a spinner while the connected Codex thread is working. Existing answers stay in the submission.
To use Claude Code, ask it to run `uv run --locked python lesson.py watch
--events` with its Monitor tool, where available, and treat each JSON
event's `message` as the student’s next lesson turn. Choose one watcher
per workspace and stop it at the end of the lesson.

## Teach the lesson.

- [Instructor guide](classroom/INSTRUCTOR.md) for classroom and live session preparation.
- [Data sources](data/README.md) for provenance and terms.

`classroom/` contains the lesson and templates, `ui/` the browser viewer,
and `model/` the forecast pipeline and reference work. `lesson.py` is the
command line. Student files are created locally in `work/`.

Original code and teaching materials are [MIT licensed](LICENSE.md). The
datasets keep their individual terms.

The course graphic uses a public-domain charging station photo by Michael
Quinn of the National Park Service and a Michigan outline derived from the
U.S. Census Bureau’s 2024 cartographic boundaries.
[Photo](https://commons.wikimedia.org/wiki/File:Grand_Canyon_National_Park_Electric_Vehicle_Charging_Stations-_Yavapai_Lodge_6654_-_48634089611.jpg) ·
[Boundaries](https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_state_20m.zip)
