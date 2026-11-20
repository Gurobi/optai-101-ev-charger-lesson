"""Lesson command line: check the setup, run a student's model, or solve the reference.

`check` and `ui` need only Python's standard library.
"""

import argparse
import csv
import importlib.util
import json
import math
import re
import shutil
import sys
import tempfile
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parent
REFERENCE = ROOT / "model" / "reference"
HALF_BUDGET = ROOT / "model" / "half_budget"
SAMPLE_BUDGETS = (1_000_000, 500_000)
WORKING = ROOT / "build" / "output"
WORK = ROOT / "work"  # the student's own model, notes, and runs
ACADEMIC_LICENSE_URL = "https://www.gurobi.com/academia/academic-program-and-licenses/"
SOLVER_WARNINGS = {
    "missing_package": "The Gurobi Python package could not be loaded.",
    "size_limited": "The installed Gurobi license is too small for the statewide model.",
    "unavailable": "Gurobi could not verify a license for the statewide model.",
}
sys.path.insert(0, str(ROOT / "model"))


def load_stage(name: str) -> ModuleType:
    path = ROOT / "model" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def reference_parameters() -> dict[str, Any]:
    """Fixed economics for the archived edition, independent of editable constants."""
    return json.loads((ROOT / "model" / "reference_parameters.json").read_text())


def current_parameters() -> dict[str, Any]:
    import constants

    # JSON normalizes level keys to strings, matching experiment configuration.
    return json.loads(
        json.dumps({name: getattr(constants, name) for name in reference_parameters()})
    )


def verify_decisions(
    solution_dir: Path,
    demand_dir: Path,
    budget: float,
    parameters: dict[str, Any] | None = None,
) -> None:
    """Evaluate standard-model plan feasibility; this does not prove optimality."""
    p = reference_parameters() if parameters is None else parameters
    if not math.isfinite(budget) or budget < 0:
        raise ValueError("Budget must be finite and nonnegative")

    demand = {row["zcta"]: row for row in read_rows(demand_dir / "zcta_demand.csv")}
    rows = read_rows(solution_dir / "solution_detail.csv")
    served: dict[str, float] = {}
    cost = revenue = 0.0
    seen = set()
    for row in rows:
        zcta, level = row["zcta"], int(row["level"])
        key = str(level)
        if level not in (2, 3) or zcta not in demand or (zcta, level) in seen:
            raise ValueError("Unknown or repeated site in solution")
        seen.add((zcta, level))
        count = float(row["count"])
        if (
            not math.isfinite(count)
            or count != int(count)
            or not p["MIN_PORTS_PER_SITE"][key] <= count <= p["MAX_PORTS_PER_SITE"][key]
        ):
            raise ValueError("Port count violates site limits")
        n_served = float(row["served"])
        utilization = float(demand[zcta][f"utilization_l{level}"])
        capacity = p["PEAK_THROUGHPUT_PER_CHARGER"][key] * utilization * count
        numbers = [
            n_served,
            capacity,
            float(row["capital"]),
            float(row["revenue_npv"]),
            float(demand[zcta]["ev_forecast"]),
        ]
        if not all(math.isfinite(value) for value in numbers):
            raise ValueError("Non-finite value in plan or demand")
        if not -0.0001 <= n_served <= capacity + 0.0001:
            raise ValueError("Served demand violates physical capacity")
        site_cost = p["SITE_FIXED_COST"][key] + p["PORT_COST"][key] * count
        site_revenue = (
            n_served * p["ANNUAL_REVENUE_PER_EV"][key] * p["LIFETIME_REVENUE_FACTOR"]
        )
        if abs(site_cost - float(row["capital"])) > 0.01:
            raise ValueError("Reported capital does not match selected ports")
        # The archived detail rounds EVs served to 4 decimals; its dollar
        # columns were computed before rounding, allowing < $0.20 per row.
        if abs(site_revenue - float(row["revenue_npv"])) > 0.20:
            raise ValueError("Reported revenue does not match discounted gross revenue")
        cost += site_cost
        revenue += float(row["revenue_npv"])
        served[zcta] = served.get(zcta, 0.0) + n_served
    if cost > budget + 0.01:
        raise ValueError("Plan exceeds budget")
    for zcta, total in served.items():
        if total > float(demand[zcta]["ev_forecast"]) + 0.0002:
            raise ValueError(
                f"Plan exceeds shared demand pool in {zcta}: its Level 2 and DC fast "
                "ports together serve more EVs than its ev_forecast. The standard "
                "check pools demand within each area, not across neighbors."
            )
    compact = read_rows(solution_dir / "solution.csv")
    if {(r["zcta"], r["level"], r["count"]) for r in compact} != {
        (r["zcta"], r["level"], r["count"]) for r in rows
    } or len(compact) != len(rows):
        raise ValueError("Compact and detailed solutions disagree")
    print(
        f"Plan checked: {len(rows)} sites, ${cost:,.0f} capital, ${revenue:,.0f} gross revenue NPV."
    )


def check() -> None:
    """Confirm the saved reference plans still satisfy the standard model."""
    verify_decisions(REFERENCE, REFERENCE, 1_000_000)
    verify_decisions(HALF_BUDGET, REFERENCE, 500_000)


def report_solver_status(status: str) -> None:
    """Publish the availability check for the live viewer and the terminal."""
    warning = SOLVER_WARNINGS.get(status)
    WORK.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=WORK) as staging:
        snapshot = Path(staging) / "solver.json"
        snapshot.write_text(json.dumps({"status": status, "warning": warning}) + "\n")
        snapshot.replace(WORK / snapshot.name)
    if warning:
        print(
            f"{warning} Continue the lesson with saved plans during Test. "
            "For live statewide solves, set up a free academic Gurobi license "
            f"where the agent runs Python. {ACADEMIC_LICENSE_URL}",
            file=sys.stderr,
        )
    else:
        print("Gurobi license check passed for the statewide exercise.")


def check_solver() -> None:
    """Check license availability without requiring a license to continue."""
    try:
        import gurobipy as gp
    except ImportError:
        report_solver_status("missing_package")
        return

    status = "unavailable"
    try:
        with gp.Env(empty=True) as env:
            env.setParam("OutputFlag", 0)
            env.start()
            with gp.Model(env=env) as model:
                model.Params.TimeLimit = 5
                # The bundled restricted license allows at most 2,000 variables.
                model.addVars(2_001, ub=1, vtype=gp.GRB.BINARY)
                model.optimize()
                if model.Status == gp.GRB.OPTIMAL:
                    status = "ready"
    except gp.GurobiError as exc:
        if exc.errno == gp.GRB.Error.SIZE_LIMIT_EXCEEDED:
            status = "size_limited"
    report_solver_status(status)


def rebuild_inputs() -> Path:
    """Regenerate features and demand from the source CSVs into build/output."""
    for stage in ["01_transform_data.py", "02_forecast_demand.py"]:
        load_stage(stage).main()
    return WORKING


def solve_reference(budget: float, rebuild: bool = False) -> Path:
    if not math.isfinite(budget) or budget < 0:
        raise ValueError("Budget must be a finite, nonnegative dollar amount")
    inputs = rebuild_inputs() if rebuild else REFERENCE
    budget_label = str(int(budget)) if budget == int(budget) else str(budget)
    output = ROOT / "build" / "runs" / f"budget-{budget_label}"
    print(f"Using {inputs.relative_to(ROOT)}; writing {output.relative_to(ROOT)}")
    load_stage("03_optimize_chargers.py").main(
        budget=budget, input_dir=inputs, output_dir=output
    )
    verify_decisions(output, inputs, budget, current_parameters())
    return output


def start_work() -> Path:
    """Fill in missing workspace files and preserve any existing work."""
    new = not WORK.exists()
    WORK.mkdir(exist_ok=True)
    for source, target in [
        (ROOT / "classroom" / "model.py", "model.py"),
        (ROOT / "classroom" / "notes.md", "notes.md"),
        (ROOT / "model" / "reference_parameters.json", "parameters.json"),
    ]:
        if (WORK / target).exists():
            continue
        contents = source.read_bytes()
        try:
            with (WORK / target).open("xb") as stream:
                stream.write(contents)
        except FileExistsError:
            pass
    if new:
        print(f"Created {WORK.relative_to(ROOT)}/ for your model, notes, and runs.")
    return WORK


def show_sample(budget: int) -> Path:
    """Copy one saved plan into the viewer workspace after the student reaches Test."""
    if budget not in SAMPLE_BUDGETS:
        raise ValueError("Saved plans are available at $1 million and $500,000.")
    archive = REFERENCE if budget == 1_000_000 else HALF_BUDGET
    examples = start_work() / "examples"
    examples.mkdir(exist_ok=True)
    output = examples / str(budget)
    if not output.exists():
        with tempfile.TemporaryDirectory(dir=examples) as staging:
            bundle = Path(staging) / "plan"
            bundle.mkdir()
            for name in ("solution_detail.csv", "gurobi.log"):
                shutil.copyfile(archive / name, bundle / name)
            summary = archive / "summary.json"
            record = json.loads(summary.read_text()) if summary.is_file() else {}
            record.update({"budget": budget, "outcome": "saved", "source": "reference"})
            (bundle / "run.json").write_text(json.dumps(record, indent=2) + "\n")
            bundle.rename(output)
    print(f"Saved reference plan at ${budget:,} is now visible in Test.")
    return output


def forecast() -> Path:
    """Build the demand forecast from the source data into work/demand.csv."""
    work = start_work()
    shutil.copyfile(rebuild_inputs() / "zcta_demand.csv", work / "demand.csv")
    print(f"Wrote {(work / 'demand.csv').relative_to(ROOT)}.")
    return work / "demand.csv"


def validate_inputs(demand: list[dict[str, str]], p: dict[str, Any]) -> None:
    expected = reference_parameters()
    if set(p) != set(expected):
        raise ValueError("Parameter names must match model/reference_parameters.json")
    for name, default in expected.items():
        value = p[name]
        if isinstance(default, dict):
            if not isinstance(value, dict) or set(value) != {"2", "3"}:
                raise ValueError(f"{name} needs level keys '2' and '3'")
            values = value.values()
        else:
            values = [value]
        for number in values:
            if isinstance(number, bool) or not isinstance(number, (int, float)):
                raise TypeError(f"{name} must contain numbers")
            if not math.isfinite(number) or number < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
    if p["LIFETIME_REVENUE_FACTOR"] <= 0:
        raise ValueError("Lifetime revenue factor must be positive")
    for level in ("2", "3"):
        low, high = p["MIN_PORTS_PER_SITE"][level], p["MAX_PORTS_PER_SITE"][level]
        if low != int(low) or high != int(high) or not 1 <= low <= high:
            raise ValueError("Site port limits must be positive ordered integers")
    seen = set()
    if not demand:
        raise ValueError("Demand must contain at least one candidate")
    for row in demand:
        zcta = row["zcta"]
        if not re.fullmatch(r"[0-9]{5}", zcta) or zcta in seen:
            raise ValueError("Demand needs unique five-digit ZCTA codes")
        seen.add(zcta)
        for field in ("ev_forecast", "utilization_l2", "utilization_l3"):
            value = float(row[field])
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"Invalid {field} for {zcta}")
            if field.startswith("utilization") and value > 1:
                raise ValueError("Utilization must be between zero and one")


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run(budget: float, time_limit: float = 60.0) -> Path:
    if not math.isfinite(budget) or budget < 0:
        raise ValueError("Budget must be finite and nonnegative")
    if not math.isfinite(time_limit) or time_limit <= 0:
        raise ValueError("Time limit must be finite and positive")
    work = start_work()
    parameters = json.loads((work / "parameters.json").read_text())
    if not (work / "demand.csv").is_file():
        raise ValueError(
            "No demand forecast yet. Do the forecast step first: lesson.py forecast"
        )
    demand = read_rows(work / "demand.csv")
    validate_inputs(demand, parameters)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    output = work / "runs" / stamp
    output.mkdir(parents=True, exist_ok=False)
    for source, target in [
        ("model.py", "model.py"),
        ("parameters.json", "parameters.json"),
        ("demand.csv", "zcta_demand.csv"),
        ("notes.md", "notes.md"),
    ]:
        shutil.copyfile(work / source, output / target)
    record: dict[str, Any] = {
        "started_utc": stamp,
        "budget": budget,
        "time_limit_seconds": time_limit,
        "outcome": "started",
        "validation_scope": "Standard lesson plan feasibility and gross-revenue arithmetic only",
    }
    record_path = output / "run.json"
    record_path.write_text(json.dumps(record, indent=2) + "\n")
    print(f"Run directory: {output.relative_to(ROOT)}", flush=True)
    model = None
    gp = None
    try:
        import gurobipy as gp

        spec = importlib.util.spec_from_file_location(
            "student_model", output / "model.py"
        )
        if spec is None or spec.loader is None:
            raise ValueError("Could not load model.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Student model construction cannot silently redefine the checker's inputs.
        model, decisions = module.build_model(
            deepcopy(demand), deepcopy(parameters), budget
        )
        model.Params.TimeLimit = time_limit
        model.Params.LogFile = str(output / "gurobi.log")
        model.optimize()
        record.update(
            {
                "solver_version": ".".join(map(str, gp.gurobi.version())),
                "solver_status": int(model.Status),
                "solution_count": int(model.SolCount),
                "runtime_seconds": model.Runtime,
            }
        )
        if model.SolCount == 0:
            record["outcome"] = "no_solution"
            raise ValueError(
                f"No incumbent solution (solver status {model.Status}); inspect your model"
            )
        record["objective"] = model.ObjVal
        gap = model.MIPGap if model.IsMIP else None
        bound = model.ObjBound if model.IsMIP else None
        record["mip_gap"] = gap if gap is not None and math.isfinite(gap) else None
        record["objective_bound"] = (
            bound if bound is not None and math.isfinite(bound) else None
        )
        by_zcta = {r["zcta"]: r for r in demand}
        rows = []
        for (zcta, level), variables in sorted(decisions.items()):
            if zcta not in by_zcta or level not in (2, 3):
                raise ValueError("Decisions contain an unknown ZCTA or charging level")
            count, served = float(variables["count"].X), float(variables["served"].X)
            if (
                not math.isfinite(count)
                or count < -1e-5
                or abs(count - round(count)) > 1e-5
            ):
                raise ValueError("Port decisions must be nonnegative integers")
            if not math.isfinite(served) or served < -1e-5:
                raise ValueError("Served demand must be finite and nonnegative")
            count = round(count)
            if count == 0:
                if abs(served) > 1e-5:
                    raise ValueError("Demand served without installed ports")
                continue
            key = str(level)
            row = by_zcta[zcta]
            utilization = float(row[f"utilization_l{level}"])
            throughput = parameters["PEAK_THROUGHPUT_PER_CHARGER"][key] * utilization
            rows.append(
                {
                    "zcta": zcta,
                    "level": level,
                    "count": count,
                    "served": served,
                    "utilization": utilization,
                    "throughput": throughput,
                    "capacity": throughput * count,
                    "ev_forecast": float(row["ev_forecast"]),
                    "capital": parameters["SITE_FIXED_COST"][key]
                    + parameters["PORT_COST"][key] * count,
                    "revenue_npv": served
                    * parameters["ANNUAL_REVENUE_PER_EV"][key]
                    * parameters["LIFETIME_REVENUE_FACTOR"],
                }
            )
        write_csv(output / "solution.csv", ["zcta", "level", "count"], rows)
        write_csv(
            output / "solution_detail.csv",
            [
                "zcta",
                "level",
                "count",
                "served",
                "utilization",
                "throughput",
                "capacity",
                "ev_forecast",
                "capital",
                "revenue_npv",
            ],
            rows,
        )
        verify_decisions(output, output, budget, parameters)
        revenue = sum(r["revenue_npv"] for r in rows)
        if model.ModelSense != gp.GRB.MAXIMIZE or not math.isclose(
            model.ObjVal, revenue, abs_tol=0.20, rel_tol=1e-8
        ):
            raise ValueError(
                "Objective does not match standard discounted gross revenue maximization"
            )
        record.update(
            {
                "outcome": "checked",
                "capital_spent": sum(r["capital"] for r in rows),
                "revenue_npv": revenue,
                "ports": sum(r["count"] for r in rows),
                "optimal_within_solver_tolerances": model.Status == gp.GRB.OPTIMAL,
            }
        )
        print(
            "Plan checks passed. Review the formulation and assumptions; these checks do not prove either correct."
        )
    except Exception as exc:
        # Preserve the failure category without copying arbitrary exception text
        # (which could contain local credentials) into the submission artifact.
        record["error_type"] = type(exc).__name__
        unavailable = None
        if gp is None and isinstance(exc, ImportError):
            unavailable = "missing_package"
        elif gp is not None and isinstance(exc, gp.GurobiError):
            if exc.errno == gp.GRB.Error.SIZE_LIMIT_EXCEEDED:
                unavailable = "size_limited"
            elif exc.errno in (gp.GRB.Error.NO_LICENSE, gp.GRB.Error.NETWORK):
                unavailable = "unavailable"
        if unavailable:
            record["outcome"] = "solver_unavailable"
            report_solver_status(unavailable)
            return output
        if record["outcome"] == "started":
            record["outcome"] = "failed"
        raise
    finally:
        record_path.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
        if model is not None:
            model.dispose()
    return output


def evaluate(budget: float, scenario: str, plan: Path | None = None) -> Path:
    """Score an allocation using the pair's forecast, rule, and independent check."""
    if not math.isfinite(budget) or budget < 0:
        raise ValueError("Budget must be finite and nonnegative")
    work = start_work()
    runs = work / "runs"
    runs.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    folder = Path(tempfile.mkdtemp(prefix=stamp + "-", dir=runs))
    record = {
        "started_utc": stamp,
        "budget": budget,
        "scenario": scenario,
        "source": "student_analysis",
        "outcome": "started",
        "allocation": "fixed plan" if plan else "new plan",
    }
    record_path = folder / "run.json"
    record_path.write_text(json.dumps(record))
    try:
        for name in ("candidates.csv", "analysis.py", "parameters.json", "notes.md"):
            shutil.copyfile(work / name, folder / name)
        candidates = read_rows(folder / "candidates.csv")
        areas = {r["zcta"] for r in candidates}
        if (
            not areas
            or len(areas) != len(candidates)
            or any(not re.fullmatch(r"[0-9]{5}", z) for z in areas)
        ):
            raise ValueError("Candidates need unique five-digit ZCTA codes")
        params = json.loads((folder / "parameters.json").read_text())
        for field in ("SITE_FIXED_COST", "PORT_COST"):
            for level in ("2", "3"):
                cost = params[field][level]
                if (
                    type(cost) not in (int, float)
                    or not math.isfinite(cost)
                    or cost < 0
                ):
                    raise ValueError(f"Invalid {field} at level {level}")
        spec = importlib.util.spec_from_file_location(
            "student_analysis", folder / "analysis.py"
        )
        if spec is None or spec.loader is None:
            raise ValueError("Could not load analysis.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for key in ("metric", "unit"):
            label = getattr(module, key.upper())
            if not isinstance(label, str) or not label.strip():
                raise ValueError(f"Provide a {key} for the score")
            record[key] = label
        if plan:
            shutil.copyfile(plan, folder / "original_plan.csv")
            choices = read_rows(folder / "original_plan.csv")
        else:
            choices = module.propose(deepcopy(candidates), deepcopy(params), budget)
        sites: list[dict[str, Any]] = []
        seen = set()
        for row in choices:
            zcta, level = row["zcta"], str(row["level"])
            count = float(row["count"])
            if zcta not in areas or level not in ("2", "3") or (zcta, level) in seen:
                raise ValueError("Unknown or repeated area and level")
            if isinstance(row["count"], bool) or not count.is_integer() or count <= 0:
                raise ValueError(
                    "List only installed sites with positive integer port counts"
                )
            seen.add((zcta, level))
            capital = (
                params["SITE_FIXED_COST"][level]
                + int(count) * params["PORT_COST"][level]
            )
            sites.append(
                {
                    "zcta": zcta,
                    "level": int(level),
                    "count": int(count),
                    "capital": capital,
                }
            )
        capital = sum(row["capital"] for row in sites)
        if capital > budget + 0.01:
            raise ValueError("Plan exceeds budget")
        score = module.check_and_score(deepcopy(sites), candidates, params, budget)
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(score)
        ):
            raise ValueError("check_and_score must return a finite numerical score")
        write_csv(folder / "solution.csv", ["zcta", "level", "count"], sites)
        write_csv(
            folder / "solution_detail.csv", ["zcta", "level", "count", "capital"], sites
        )
        record.update(
            outcome="checked",
            objective=score,
            capital_spent=capital,
            ports=sum(row["count"] for row in sites),
        )
    except Exception as exc:
        record.update(outcome="failed", error_type=type(exc).__name__)
        raise
    finally:
        record_path.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
    print(
        f"{scenario}: {score:g} {record['unit']}, ${capital:,.0f} capital ({folder.relative_to(ROOT)})"
    )
    return folder


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check_cmd = commands.add_parser("check", help="Verify the saved reference plans")
    check_cmd.add_argument(
        "--solver",
        action="store_true",
        help="Check live statewide solve availability and warn if unavailable",
    )
    run_cmd = commands.add_parser("run", help="Solve and check the model in work/")
    run_cmd.add_argument("--budget", type=float, default=1_000_000)
    run_cmd.add_argument("--time-limit", type=float, default=60)
    evaluate_cmd = commands.add_parser(
        "evaluate", help="Check and score a student-defined allocation"
    )
    evaluate_cmd.add_argument("--budget", type=float, default=1_000_000)
    evaluate_cmd.add_argument("--scenario", default="Baseline")
    evaluate_cmd.add_argument(
        "--plan",
        type=Path,
        help="Rescore an existing solution.csv with fixed port counts",
    )
    commands.add_parser("forecast", help="Build work/demand.csv from the source data")
    sample = commands.add_parser("sample", help="Show a saved reference plan in Test")
    sample.add_argument("--budget", type=int, choices=SAMPLE_BUDGETS, default=1_000_000)
    reference = commands.add_parser("reference", help="Solve the reference model")
    reference.add_argument("--budget", type=float, default=1_000_000)
    reference.add_argument(
        "--rebuild",
        action="store_true",
        help="Regenerate demand from the source CSVs instead of using saved demand",
    )
    ui = commands.add_parser("ui", help="Serve the browser viewer and response editor")
    ui.add_argument("--host", default="127.0.0.1")
    ui.add_argument("--port", type=int, default=8765)
    watch = commands.add_parser("watch", help="Watch for saved student answers")
    watch_target = watch.add_mutually_exclusive_group()
    watch_target.add_argument("--thread", help="Send to this Codex conversation")
    watch_target.add_argument(
        "--events",
        action="store_true",
        help="Write answer events for a Claude Code monitor",
    )
    args = parser.parse_args()
    try:
        if args.command == "ui":
            from ui.server import serve

            start_work()
            serve(args.host, args.port)
        elif args.command == "watch":
            from classroom.watch import watch as watch_responses

            try:
                watch_responses(args.thread, args.events)
            except KeyboardInterrupt:
                pass
        elif args.command == "check":
            if args.solver:
                check_solver()
            else:
                check()
        elif args.command == "evaluate":
            evaluate(args.budget, args.scenario, args.plan)
        elif args.command == "forecast":
            forecast()
        elif args.command == "run":
            run(args.budget, args.time_limit)
        elif args.command == "sample":
            show_sample(args.budget)
        else:
            solve_reference(args.budget, args.rebuild)
    except (
        ValueError,
        OSError,
        ImportError,
        NotImplementedError,
        KeyError,
        TypeError,
    ) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
