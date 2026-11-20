"""Check the work folder, invalid plans, and the data pipeline.

Solver integration tests are opt-in: RUN_SOLVER_TESTS=1 uses the installed
Gurobi license. The ordinary CI suite needs no solver credentials.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from threading import Thread
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import lesson


class WorkspaceCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # Keep paths under ROOT so diagnostic paths have the same shape as class.
        self.patches = [
            patch.object(lesson, "WORK", Path(self.temp.name) / "work"),
            patch.object(lesson, "ROOT", Path(self.temp.name)),
        ]
        for folder in ("model", "classroom"):
            shutil.copytree(lesson.ROOT / folder, Path(self.temp.name) / folder)
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)


class ExperimentTests(WorkspaceCase):
    def test_start_preserves_existing_work_and_leading_zero_codes(self):
        path = lesson.start_work()
        self.assertFalse((path / "demand.csv").exists())
        with self.assertRaisesRegex(ValueError, "forecast"):
            lesson.run(1_000_000)
        (path / "notes.md").write_text("Our prediction")
        (path / "parameters.json").unlink()
        lesson.start_work()
        self.assertEqual((path / "notes.md").read_text(), "Our prediction")
        self.assertTrue((path / "parameters.json").is_file())
        demand = [
            {
                "zcta": "00123",
                "ev_forecast": "1",
                "utilization_l2": ".5",
                "utilization_l3": ".5",
            }
        ]
        lesson.validate_inputs(demand, lesson.reference_parameters())
        self.assertEqual(demand[0]["zcta"], "00123")

    def test_custom_plan_can_be_rescored_without_reallocating(self):
        from ui import server

        path = lesson.start_work()
        (path / "analysis.py").write_text("""METRIC = "Reach"
UNIT = "households"
def propose(candidates, parameters, budget):
    best = max(candidates, key=lambda r: int(r["households"]))
    return [dict(zcta=best["zcta"], level=2, count=1)]
def check_and_score(sites, candidates, parameters, budget):
    if len(sites) != 1:
        raise ValueError("Pilot requires exactly one site")
    return next(int(r["households"]) for r in candidates if r["zcta"] == sites[0]["zcta"])
""")
        candidates = path / "candidates.csv"
        candidates.write_text("zcta,households\n00123,20\n00124,10\n")
        baseline = lesson.evaluate(24_000, "Baseline")
        candidates.write_text("zcta,households\n00123,5\n00124,10\n")
        original = baseline / "solution.csv"
        stress = lesson.evaluate(24_000, "Lower reach", original)
        redesign = lesson.evaluate(24_000, "New site")
        for folder, score in [(baseline, 20), (stress, 5), (redesign, 10)]:
            result = server.plan(folder)
            self.assertEqual(result["record"]["objective"], score)
            self.assertEqual(result["record"]["unit"], "households")
            self.assertEqual(result["record"]["capital_spent"], 18_000)
        self.assertEqual(server.plan(stress)["sites"], server.plan(baseline)["sites"])
        self.assertNotEqual(
            candidates.read_text(), (baseline / "candidates.csv").read_text()
        )
        with self.assertRaisesRegex(ValueError, "budget"):
            lesson.evaluate(10_000, "Unaffordable", original)
        original = path / "empty.csv"
        original.write_text("zcta,level,count\n")
        with self.assertRaisesRegex(ValueError, "exactly one"):
            lesson.evaluate(24_000, "Empty", original)
        original.write_text("zcta,level,count\n00123,2,1.5\n")
        with self.assertRaisesRegex(ValueError, "integer"):
            lesson.evaluate(24_000, "Fractional", original)
        failed = [
            server.plan(f)
            for f in (path / "runs").iterdir()
            if server.plan(f)["record"]["outcome"] == "failed"
        ]
        self.assertEqual(len(failed), 3)
        self.assertTrue(all(not result["sites"] for result in failed))

    def test_invalid_inputs(self):
        demand = lesson.read_rows(lesson.REFERENCE / "zcta_demand.csv")[:1]
        p = lesson.reference_parameters()
        for value in (-1, float("nan"), float("inf")):
            with self.subTest(value=value):
                p["PORT_COST"]["2"] = value
                with self.assertRaises(ValueError):
                    lesson.validate_inputs(demand, p)
        p = lesson.reference_parameters()
        for field, value in (("utilization_l2", "1.1"), ("ev_forecast", "nan")):
            bad = [dict(demand[0], **{field: value})]
            with self.assertRaises(ValueError):
                lesson.validate_inputs(bad, p)
        with self.assertRaises(ValueError):
            lesson.validate_inputs(demand * 2, p)

    def test_reference_parameters_match_original_constants(self):
        self.assertEqual(lesson.reference_parameters(), lesson.current_parameters())

    def test_reference_checks_do_not_follow_edited_costs(self):
        import constants

        with patch.dict(constants.PORT_COST, {2: 999999}):
            lesson.verify_decisions(lesson.REFERENCE, lesson.REFERENCE, 1_000_000)
            with self.assertRaises(ValueError):
                lesson.verify_decisions(
                    lesson.REFERENCE,
                    lesson.REFERENCE,
                    1_000_000,
                    lesson.current_parameters(),
                )

    def test_plan_checker_rejects_nonfinite_budget_and_reported_values(self):
        for value in (float("nan"), float("inf"), -1):
            with self.assertRaises(ValueError):
                lesson.verify_decisions(lesson.REFERENCE, lesson.REFERENCE, value)
        plan = Path(self.temp.name) / "plan"
        plan.mkdir()
        rows = lesson.read_rows(lesson.REFERENCE / "solution_detail.csv")
        rows[0]["capital"] = "nan"
        lesson.write_csv(plan / "solution_detail.csv", list(rows[0]), rows)
        shutil.copyfile(lesson.REFERENCE / "solution.csv", plan / "solution.csv")
        with self.assertRaisesRegex(ValueError, "Non-finite"):
            lesson.verify_decisions(plan, lesson.REFERENCE, 1_000_000)

    def test_plan_checker_rejects_budget_and_capacity_violations(self):
        with self.assertRaisesRegex(ValueError, "budget"):
            lesson.verify_decisions(lesson.REFERENCE, lesson.REFERENCE, 0)
        plan = Path(self.temp.name) / "plan"
        plan.mkdir()
        rows = lesson.read_rows(lesson.REFERENCE / "solution_detail.csv")
        rows[0]["served"] = "100000000"
        lesson.write_csv(plan / "solution_detail.csv", list(rows[0]), rows)
        with self.assertRaisesRegex(ValueError, "capacity"):
            lesson.verify_decisions(plan, lesson.REFERENCE, 1_000_000)

    def test_invalid_budget_does_not_create_a_run(self):
        path = lesson.start_work()
        with self.assertRaises(ValueError):
            lesson.run(float("nan"))
        self.assertFalse((path / "runs").exists())

    def test_license_preflight_warns_and_clears_viewer_notice(self):
        import gurobipy as gp

        from ui import server

        output = StringIO()
        with (
            patch.object(server, "ROOT", lesson.ROOT),
            patch.object(gp, "Env") as env,
            patch.object(gp, "Model") as model,
            redirect_stderr(output),
        ):
            start = env.return_value.__enter__.return_value.start
            probe = model.return_value.__enter__.return_value
            start.side_effect = gp.GurobiError(gp.GRB.Error.NO_LICENSE, "private setup")
            lesson.check_solver()
            work = server.live()
            assert work is not None
            self.assertEqual(work["solver"]["status"], "unavailable")
            self.assertEqual(work["examples"], [])

            start.side_effect = None
            probe.optimize.side_effect = gp.GurobiError(
                gp.GRB.Error.SIZE_LIMIT_EXCEEDED, "private setup"
            )
            lesson.check_solver()
            work = server.live()
            assert work is not None
            self.assertEqual(work["solver"]["status"], "size_limited")
            self.assertIn("too small", work["solver"]["warning"])

            probe.optimize.side_effect = None
            probe.Status = gp.GRB.OPTIMAL
            lesson.check_solver()
            work = server.live()
            assert work is not None
            self.assertEqual(work["solver"], {"status": "ready", "warning": None})
        self.assertIn(lesson.ACADEMIC_LICENSE_URL, output.getvalue())
        self.assertNotIn("private setup", output.getvalue())

    def test_run_preserves_attempt_when_gurobi_is_unavailable(self):
        from ui import server

        path = lesson.start_work()
        shutil.copyfile(lesson.REFERENCE / "zcta_demand.csv", path / "demand.csv")
        source = """import gurobipy as gp
def build_model(demand, parameters, budget):
    raise gp.GurobiError(gp.GRB.Error.SIZE_LIMIT_EXCEEDED, "private setup")
"""
        (path / "model.py").write_text(source)
        with patch.object(server, "ROOT", lesson.ROOT), redirect_stderr(StringIO()):
            with patch.dict(sys.modules, {"gurobipy": None}):
                lesson.check_solver()
                missing = lesson.run(1_000_000)
            work = server.live()
            assert work is not None
            self.assertEqual(work["solver"]["status"], "missing_package")

            limited = lesson.run(1_000_000)
            work = server.live()
            assert work is not None
            self.assertEqual(work["solver"]["status"], "size_limited")
            self.assertEqual(work["examples"], [])
        for attempt in (missing, limited):
            with self.subTest(attempt=attempt.name):
                self.assertEqual((attempt / "model.py").read_text(), source)
                self.assertFalse((attempt / "solution.csv").exists())
                run = server.plan(attempt)
                self.assertEqual(run["record"]["outcome"], "solver_unavailable")
                self.assertEqual(run["sites"], [])
                self.assertNotIn("private setup", (attempt / "run.json").read_text())

    def test_viewer_reads_inputs_and_work(self):
        from ui import server

        self.assertEqual(len(server.areas()), 992)
        with patch.object(server, "ROOT", Path(self.temp.name)):
            self.assertIsNone(server.live())
            lesson.start_work()
            work = server.live()
            assert work is not None
            self.assertEqual(set(work["notes"].values()), {""})
            (lesson.WORK / "notes.md").write_text(
                "# Notes.\n\n## Explore the data.\n<!-- guide -->\n- 992 areas\n\n"
                "## Run the model.\nRun.\n## Read the solver log.\nGap.\n"
                "## Recommend.\nBuild.\n"
            )
            work = server.live()
            assert work is not None
            notes = work["notes"]
            self.assertEqual(notes["data"], "- 992 areas")
            self.assertEqual(notes["test"], "Run.\n\nGap.")
            self.assertEqual(notes["recommend"], "Build.")
            self.assertEqual(notes["formulate"], "")
            self.assertEqual(work["runs"], [])
            self.assertEqual(work["examples"], [])
        self.assertNotIn("WLS", server.screen_safe("WLS license 1\nOptimize"))
        self.assertEqual(
            server.screen_safe("Set parameter LicenseID to value 1\nOptimize"),
            "Optimize",
        )

    def test_saved_plans_are_loaded_one_budget_at_a_time(self):
        from ui import server

        with patch.object(server, "ROOT", lesson.ROOT):
            first = lesson.show_sample(1_000_000)
            self.assertEqual(first, lesson.show_sample(1_000_000))
            work = server.live()
            assert work is not None
            self.assertEqual(work["runs"], [])
            self.assertEqual(len(work["examples"]), 1)
            self.assertEqual(work["examples"][0]["budget"], 1_000_000)
            self.assertEqual(work["examples"][0]["record"]["outcome"], "saved")
            self.assertEqual(len(work["examples"][0]["sites"]), 12)
            lesson.show_sample(500_000)
            work = server.live()
            assert work is not None
            self.assertEqual(
                [p["budget"] for p in work["examples"]], [1_000_000, 500_000]
            )
            self.assertEqual(len(work["examples"][1]["sites"]), 6)

    def test_viewer_charts_have_their_data(self):
        from ui import server

        rows = server.demand(lesson.REFERENCE / "zcta_demand.csv")
        self.assertEqual(len(rows), 992)
        self.assertTrue(all(0 <= r[2] <= 1 and 0 <= r[3] <= 1 for r in rows))
        self.assertEqual(server.demand(Path(self.temp.name) / "missing.csv"), [])

    def test_viewer_moves_to_a_free_port(self):
        from ui import server

        first = server.bind("127.0.0.1", 0)
        self.addCleanup(first.server_close)
        busy = first.server_address[1]
        second = server.bind("127.0.0.1", busy, tries=50)
        self.addCleanup(second.server_close)
        self.assertNotEqual(second.server_address[1], busy)
        with self.assertRaisesRegex(OSError, "in use"):
            server.bind("127.0.0.1", busy, tries=1)

    def test_viewer_saves_and_exports_student_responses(self):
        from ui import server

        with (
            patch.object(server, "ROOT", lesson.ROOT),
            server.bind("127.0.0.1", 0) as http,
        ):
            address = f"http://127.0.0.1:{http.server_address[1]}"
            listener = Thread(target=http.serve_forever)
            listener.start()

            def send(step, answer):
                request = Request(
                    address + "/api/responses",
                    data=json.dumps({"step": step, "answer": answer}).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(request, timeout=3) as reply:
                    return json.load(reply)["answer"]

            try:
                answer = "Keep ZIP 48001.\n\n## Literal student text <example>."
                self.assertEqual(send("data/observe", answer), answer)
                self.assertEqual(
                    send("test/predict", "We expect fewer ports."),
                    "We expect fewer ports.",
                )
                self.assertEqual(
                    send("data/observe", answer + "\nPlan a pilot."),
                    answer + "\nPlan a pilot.",
                )
                with self.assertRaises(HTTPError) as raised:
                    send("../outside", "Unexpected destination")
                self.assertEqual(raised.exception.code, 400)
                with urlopen(address + "/api/responses", timeout=3) as reply:
                    self.assertEqual(
                        json.load(reply),
                        {
                            "data/observe": answer + "\nPlan a pilot.",
                            "test/predict": "We expect fewer ports.",
                        },
                    )
                with urlopen(address + "/student-responses.md", timeout=3) as reply:
                    self.assertIn(
                        "student-responses.md", reply.headers["Content-Disposition"]
                    )
                    submission = reply.read().decode()
                self.assertIn("    ## Literal student text <example>.", submission)
                self.assertLess(
                    submission.index("## Explore · Observe"),
                    submission.index("## Test · Predict"),
                )
                lesson.start_work()
                path = lesson.WORK / "responses" / "data" / "observe.txt"
                self.assertEqual(
                    path.read_text(encoding="utf-8"), answer + "\nPlan a pilot."
                )
            finally:
                http.shutdown()
                listener.join()

    def test_interactive_figure_is_served_with_an_isolated_document_policy(self):
        from ui import server

        folder = lesson.WORK / "figures"
        folder.mkdir(parents=True)
        figure = folder / "charger-map.html"
        figure.write_text("<title>Charger map</title>", encoding="utf-8")
        with (
            patch.object(server, "ROOT", lesson.ROOT),
            server.bind("127.0.0.1", 0) as http,
        ):
            listener = Thread(target=http.serve_forever)
            listener.start()
            try:
                address = f"http://127.0.0.1:{http.server_address[1]}"
                with urlopen(address + "/figures/charger-map.html", timeout=3) as reply:
                    self.assertEqual(reply.headers.get_content_type(), "text/html")
                    policy = reply.headers["Content-Security-Policy"]
                    self.assertIn("sandbox allow-scripts", policy)
                    self.assertNotIn("allow-same-origin", policy)
                    self.assertEqual(reply.read(), b"<title>Charger map</title>")
                original = server.live()
                assert original is not None
                timestamp = figure.stat().st_mtime_ns + 1_000_000_000
                os.utime(figure, ns=(timestamp, timestamp))
                changed = server.live()
                assert changed is not None
                self.assertNotEqual(original["figures"], changed["figures"])
            finally:
                http.shutdown()
                listener.join()

    def test_watch_attaches_to_parent_thread_and_sends_from_lesson(self):
        from classroom import watch

        parent = Path(self.temp.name).resolve()
        root = parent / "lesson"
        with patch.object(watch, "ROOT", root), patch.object(
            watch.CodexThread, "call"
        ) as call:
            agent = watch.CodexThread(Mock())
            call.reset_mock()
            call.return_value = {"thread": {"cwd": str(parent)}}
            self.assertEqual(agent.attach("existing-thread"), "existing-thread")
            call.assert_called_once_with(
                "thread/read", {"threadId": "existing-thread", "includeTurns": False}
            )

            call.return_value = {"turn": {"id": "saved-answer"}}
            self.assertEqual(
                agent.send("existing-thread", "Student answer", "idle"), "saved-answer"
            )
            method, params = call.call_args.args
            self.assertEqual(method, "turn/start")
            self.assertEqual(params["threadId"], "existing-thread")
            self.assertEqual(params["cwd"], str(root))

            call.return_value = {"thread": {"cwd": str(parent / "less")}}
            with self.assertRaisesRegex(ValueError, "lesson folder or a parent folder"):
                agent.attach("unrelated-thread")

    def test_watch_queues_only_changed_responses(self):
        from classroom.watch import collect_changes, student_message

        original = {"data/brief": "Company leadership"}
        pending = {}
        collect_changes(original, original, pending)
        self.assertEqual(pending, {})

        current = {**original, "data/ask": "Compare two ZIP areas"}
        collect_changes(original, current, pending)
        revised = {**current, "data/ask": "Compare ZIP 48001 and 48002"}
        collect_changes(current, revised, pending)
        self.assertEqual(pending, {"data/ask": revised["data/ask"]})
        message = student_message("data/ask", pending["data/ask"])
        self.assertIn("Explore → Ask", message)
        self.assertIn("Name what to compare", message)
        self.assertIn("Compare ZIP 48001 and 48002", message)
        collect_changes(revised, original, pending)
        self.assertEqual(pending, {})

    def test_table_notes_only_queue_explicit_agent_requests(self):
        from classroom.watch import collect_changes, student_message

        key = "data/stations"
        pending = {}
        previous = {}
        for note, queued in (
            ("Count public ports?", False),
            ("Ask @agent later.", False),
            ("@agentic wording", False),
            ("@agent", False),
            ("@agent What does access mean?", True),
            ("I found the access field.", False),
            ("@Agent: Which rows are public?", True),
            ("", False),
        ):
            current = {key: note} if note else {}
            collect_changes(previous, current, pending)
            self.assertEqual(pending, current if queued else {})
            previous = current
        self.assertIn("Charging stations", student_message(key, "@agent Check access"))

    def test_viewer_reply_matches_the_saved_table_note(self):
        from classroom.watch import student_message
        from ui import server

        key = "data/zip-2022"
        note = "@agent Is this on?"
        with patch.object(server, "ROOT", lesson.ROOT):
            lesson.start_work()
            server.save_response(key, note)
            path = server.table_reply_path(key, note)
            self.assertIn(str(path), student_message(key, note))
            destination = lesson.ROOT / path
            destination.parent.mkdir(parents=True)
            destination.write_text("Yes, I got your note.")
            self.assertEqual(
                server.table_replies(),
                {key: {"note": note, "reply": "Yes, I got your note."}},
            )
            self.assertNotIn("Yes, I got your note.", server.response_download())
            server.save_response(key, "@agent What is FREQUENCY?")
            self.assertEqual(server.table_replies(), {})

    def test_viewer_reply_tracks_the_saved_prompt_version(self):
        from ui import server

        with patch.object(server, "ROOT", lesson.ROOT):
            key = "forecast/method"
            server.save_response(key, "First method")
            path = lesson.ROOT / server.table_reply_path(key, "First method")
            path.parent.mkdir(parents=True)
            path.write_text("Please specify units.")
            self.assertEqual(server.agent_replies()[key]["reply"], "Please specify units.")
            server.save_response(key, "Revised method")
            self.assertNotIn(key, server.agent_replies())

    def test_shared_demand_error_names_the_area(self):
        plan = Path(self.temp.name) / "plan"
        plan.mkdir()
        rows = lesson.read_rows(lesson.REFERENCE / "solution_detail.csv")
        demand = Path(self.temp.name) / "inputs"
        demand.mkdir()
        cells = lesson.read_rows(lesson.REFERENCE / "zcta_demand.csv")
        for cell in cells:
            if cell["zcta"] == rows[0]["zcta"]:
                cell["ev_forecast"] = "1"
        lesson.write_csv(demand / "zcta_demand.csv", list(cells[0]), cells)
        shutil.copyfile(
            lesson.REFERENCE / "solution_detail.csv", plan / "solution_detail.csv"
        )
        shutil.copyfile(lesson.REFERENCE / "solution.csv", plan / "solution.csv")
        with self.assertRaisesRegex(
            ValueError, f"pool in {rows[0]['zcta']}.*not across"
        ):
            lesson.verify_decisions(plan, demand, 1_000_000)

    def test_rebuilt_inputs_match_saved_reference(self):
        import pandas as pd

        for item in self.patches:
            item.stop()
        rebuilt = lesson.rebuild_inputs()
        for name in ("zcta_features.csv", "zcta_demand.csv"):
            pd.testing.assert_frame_equal(
                pd.read_csv(rebuilt / name, dtype={"zcta": str}),
                pd.read_csv(lesson.REFERENCE / name, dtype={"zcta": str}),
                check_exact=False,
                rtol=1e-10,
                atol=1e-10,
            )
        self.assertEqual(
            json.loads((rebuilt / "state_context.json").read_text()),
            json.loads((lesson.REFERENCE / "state_context.json").read_text()),
        )


@unittest.skipUnless(
    os.environ.get("RUN_SOLVER_TESTS") == "1", "solver tests are opt-in"
)
class SolverIntegrationTests(WorkspaceCase):
    def make_model(self):
        path = lesson.start_work()
        rows = [
            {
                "zcta": "00123",
                "ev_forecast": "100",
                "utilization_l2": "1",
                "utilization_l3": "1",
            }
        ]
        lesson.write_csv(path / "demand.csv", list(rows[0]), rows)
        (path / "model.py").write_text("""import gurobipy as gp
def build_model(demand, parameters, budget):
    p = parameters
    model = gp.Model()
    y = model.addVar(vtype=gp.GRB.BINARY)
    x = model.addVar(vtype=gp.GRB.INTEGER)
    s = model.addVar()
    model.addConstr(x >= p["MIN_PORTS_PER_SITE"]["2"] * y)
    model.addConstr(x <= p["MAX_PORTS_PER_SITE"]["2"] * y)
    model.addConstr(s <= p["PEAK_THROUGHPUT_PER_CHARGER"]["2"] * x)
    model.addConstr(s <= float(demand[0]["ev_forecast"]))
    model.addConstr(p["SITE_FIXED_COST"]["2"] * y + p["PORT_COST"]["2"] * x <= budget)
    model.setObjective(s * p["ANNUAL_REVENUE_PER_EV"]["2"] * p["LIFETIME_REVENUE_FACTOR"], gp.GRB.MAXIMIZE)
    return model, {("00123", 2): {"count": x, "served": s}}
""")
        return path

    def test_run_preserves_scenario_inputs_and_zero_budget(self):
        path = self.make_model()
        first = lesson.run(24000)
        self.assertEqual(json.loads((first / "run.json").read_text())["ports"], 2)
        p = json.loads((path / "parameters.json").read_text())
        p["PORT_COST"]["2"] = 9000
        (path / "parameters.json").write_text(json.dumps(p))
        second = lesson.run(24000)
        self.assertEqual(json.loads((second / "run.json").read_text())["ports"], 0)
        self.assertEqual(
            json.loads((first / "parameters.json").read_text())["PORT_COST"]["2"], 6000
        )
        self.assertNotEqual(first, second)
        zero = lesson.run(0)
        self.assertEqual(lesson.read_rows(zero / "solution.csv"), [])

    def test_incorrect_objective_is_preserved_as_failure(self):
        from ui import server

        path = self.make_model()
        source = (
            (path / "model.py")
            .read_text()
            .replace(
                's * p["ANNUAL_REVENUE_PER_EV"]["2"]',
                '2 * s * p["ANNUAL_REVENUE_PER_EV"]["2"]',
            )
        )
        (path / "model.py").write_text(source)
        with self.assertRaisesRegex(ValueError, "Objective"):
            lesson.run(24000)
        runs = list((path / "runs").iterdir())
        self.assertEqual(len(runs), 1)
        self.assertEqual((runs[0] / "model.py").read_text(), source)
        self.assertEqual(
            json.loads((runs[0] / "run.json").read_text())["outcome"], "failed"
        )
        self.assertEqual(server.plan(runs[0])["sites"], [])

    def test_infeasible_model_records_status_without_a_plan(self):
        path = self.make_model()
        source = (
            (path / "model.py")
            .read_text()
            .replace(
                "    model.setObjective(",
                "    model.addConstr(x <= -1)\n    model.setObjective(",
            )
        )
        (path / "model.py").write_text(source)
        with self.assertRaisesRegex(ValueError, "No incumbent"):
            lesson.run(24000)
        output = next((path / "runs").iterdir())
        record = json.loads((output / "run.json").read_text())
        self.assertEqual(record["outcome"], "no_solution")
        self.assertEqual(record["solution_count"], 0)
        self.assertFalse((output / "solution.csv").exists())


if __name__ == "__main__":
    unittest.main()
