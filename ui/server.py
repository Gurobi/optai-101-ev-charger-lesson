"""Serve the lesson and live workspace artifacts using the standard library."""

import csv
import errno
import hashlib
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from time import time
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "ui"
MAX_RUNS = 20
MAX_RESPONSE = 8000
MAX_RESPONSE_BODY = 6 * MAX_RESPONSE + 256
FIGURE_PATH = re.compile(r"/figures/[A-Za-z0-9_-]+\.(png|svg|html)")
FIGURE_TYPES = {
    "png": "image/png",
    "svg": "image/svg+xml",
    "html": "text/html; charset=utf-8",
}
FIGURE_POLICIES = {
    "svg": "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:",
    "html": (
        "sandbox allow-scripts allow-downloads; default-src 'none'; "
        "script-src 'unsafe-inline' blob:; style-src 'unsafe-inline'; "
        "img-src https: data: blob:; font-src https: data:; "
        "connect-src https:; worker-src blob:; base-uri 'none'; form-action 'none'"
    ),
}
STEPS_FILE = ROOT / "classroom" / "steps.json"
STEPS = json.loads(STEPS_FILE.read_text(encoding="utf-8"))
NOTE_HEADINGS = {
    heading.lower(): step["id"]
    for step in STEPS
    for heading in [step["name"], *step["oldHeadings"]]
}
RESPONSE_STEPS = {
    f"{phase['id']}/{step['id']}": (phase["name"], step)
    for phase in STEPS
    for step in phase["subsections"]
    if step.get("response")
}
STATIC = {
    "/": (UI / "index.html", "text/html; charset=utf-8"),
    "/viewer.css": (UI / "viewer.css", "text/css; charset=utf-8"),
    "/viewer.js": (UI / "viewer.js", "text/javascript; charset=utf-8"),
    "/notes.js": (UI / "notes.js", "text/javascript; charset=utf-8"),
    "/gurobi-logo.svg": (UI / "gurobi-logo.svg", "image/svg+xml"),
    "/ev-charging-station.webp": (UI / "ev-charging-station.webp", "image/webp"),
    "/michigan-outline.png": (UI / "michigan-outline.png", "image/png"),
    "/api/steps": (STEPS_FILE, "application/json"),
}
SOURCE_TABLES = {
    "/api/data/stations": "michigan_ev_charger_locations/michigan_ev_charger_locations.csv",
    "/api/data/zip-2022": "michigan_ev_registration/michigan_ev_registration_by_zip_semcog_2022.csv",
    "/api/data/zip-2023": "michigan_ev_registration/michigan_ev_registration_by_zip_semcog_2023.csv",
    "/api/data/state-2025": "michigan_ev_registration/michigan_ev_registration_state_totals_afdc.csv",
    "/api/data/population": "michigan_population/michigan_zcta_population_2013_2023.csv",
    "/api/data/centroids": "michigan_zcta_centroids/michigan_zcta_centroids_2023.csv",
}


def source_table(path: Path) -> dict[str, list[str] | list[list[str]]]:
    """Keep the source column order and the original text of each cell."""
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.reader(stream)
        return {"columns": next(reader, []), "rows": list(reader)}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def response_path(key: str) -> Path:
    return ROOT / "work" / "responses" / (key + ".txt")


def table_reply_path(key: str, note: str) -> Path:
    # An edit can arrive while the agent is answering the previous note.
    digest = hashlib.sha256(note.encode("utf-8")).hexdigest()
    return Path("work", "replies", key, f"{digest}.txt")


def table_replies() -> dict[str, dict[str, str]]:
    replies = {}
    for key, (_, step) in RESPONSE_STEPS.items():
        if step.get("source") and (note := read_text(response_path(key))):
            reply = read_text(ROOT / table_reply_path(key, note)).strip()
            if reply:
                replies[key] = {"note": note, "reply": reply}
    return replies


def agent_replies() -> dict[str, dict[str, Any]]:
    replies = {}
    for key, (_, step) in RESPONSE_STEPS.items():
        if not step.get("source") and (answer := read_text(response_path(key))):
            path = ROOT / table_reply_path(key, answer)
            reply = read_text(path).strip()
            if reply:
                replies[key] = {"answer": answer, "reply": reply, "updated": path.stat().st_mtime_ns}
    return replies


def responses() -> dict[str, str]:
    return {
        key: answer
        for key in RESPONSE_STEPS
        if (answer := read_text(response_path(key)))
    }


def save_response(key: str, answer: str) -> None:
    path = response_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=path.parent) as folder:
        temporary = Path(folder) / path.name
        temporary.write_text(answer, encoding="utf-8", newline="\n")
        temporary.replace(path)


def response_download() -> str:
    sections = ["# Michigan EV charging lesson responses"]
    for key, answer in responses().items():
        phase, step = RESPONSE_STEPS[key]
        literal = "\n".join("    " + line for line in answer.split("\n"))
        sections.append(
            f"## {phase} · {step['label']}\n\n{step['response']}\n\n{literal}"
        )
    return "\n\n".join(sections) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return {}


def screen_safe(log: str) -> str:
    """Drop the lines that show a local path or license ID on a shared screen."""
    hidden = (
        "Set parameter LogFile",
        "Set parameter LicenseID",
        "Set parameter WLS",
        "WLS license",
        "Academic license",
    )
    return "\n".join(line for line in log.splitlines() if not line.startswith(hidden))


def plan(folder: Path) -> dict[str, Any]:
    """One solved plan: its record, solver log, and selected sites."""
    detail = folder / "solution_detail.csv"
    record = read_json(folder / "run.json")
    return {
        "id": folder.name,
        "budget": record.get("budget"),
        "record": record,
        "log": screen_safe(read_text(folder / "gurobi.log")),
        "sites": read_rows(detail)
        if record.get("outcome") in ("checked", "saved") and detail.is_file()
        else [],
    }


def areas() -> list[list[Any]]:
    """Where each ZIP area is, so the page can draw maps."""
    rows = read_rows(
        ROOT / "data/michigan_zcta_centroids/michigan_zcta_centroids_2023.csv"
    )
    return [[r["zcta"], float(r["lat"]), float(r["lon"])] for r in rows]


def note_sections(text: str) -> dict[str, str]:
    """Split notes.md into one entry per step, dropping guidance comments."""
    notes: dict[str, str] = {step["id"]: "" for step in STEPS}
    key = None
    fenced = False
    for line in re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith("## "):
            key = NOTE_HEADINGS.get(line[3:].strip().rstrip(".").lower())
            if key and notes[key]:
                notes[key] += "\n"
        elif key:
            notes[key] += line + "\n"
    return {k: v.strip() for k, v in notes.items()}


def demand(path: Path) -> list[list[Any]]:
    """The forecast in work/, as [zcta, EVs, Level 2 use, DC fast use]."""
    if not path.is_file():
        return []
    try:
        return [
            [
                r["zcta"],
                float(r["ev_forecast"]),
                float(r["utilization_l2"]),
                float(r["utilization_l3"]),
            ]
            for r in read_rows(path)
        ]
    except KeyError, ValueError:
        return []


def agent_active(work: Path) -> bool:
    # The watcher refreshes this marker while Codex is working. Expire it if
    # the watcher is killed before it can clear the marker.
    try:
        return time() - (work / ".agent-active").stat().st_mtime < 10
    except FileNotFoundError:
        return False


def live() -> dict[str, Any] | None:
    """The student's own work, or None before anything has been created."""
    folder = ROOT / "work"
    if not folder.is_dir():
        return None
    runs = sorted(
        (p for p in (folder / "runs").glob("*") if (p / "run.json").is_file()),
        reverse=True,
    )[:MAX_RUNS]
    examples = sorted(
        (
            p
            for p in (folder / "examples").glob("*")
            if p.name.isdecimal() and (p / "run.json").is_file()
        ),
        key=lambda p: int(p.name),
        reverse=True,
    )
    figures = {}
    for path in (folder / "figures").glob("*"):
        if FIGURE_PATH.fullmatch(f"/figures/{path.name}"):
            try:
                figures[path.name] = str(path.stat().st_mtime_ns)
            except FileNotFoundError:
                continue
    return {
        "agent_active": agent_active(folder),
        "table_replies": table_replies(),
        "agent_replies": agent_replies(),
        "notes": note_sections(read_text(folder / "notes.md")),
        "model": read_text(folder / "model.py"),
        "analysis": read_text(folder / "analysis.py"),
        "parameters": read_json(folder / "parameters.json"),
        "solver": read_json(folder / "solver.json"),
        "demand": demand(folder / "demand.csv"),
        "runs": [plan(run) for run in runs],
        "examples": [plan(example) for example in examples],
        "figures": figures,
    }


class Handler(BaseHTTPRequestHandler):
    def send(
        self,
        body: bytes,
        kind: str,
        status: int = 200,
        download: str | None = None,
        policy: str | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if policy:
            self.send_header("Content-Security-Policy", policy)
            self.send_header("Referrer-Policy", "no-referrer")
        if download:
            self.send_header(
                "Content-Disposition", f'attachment; filename="{download}"'
            )
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        url = urlparse(self.path)
        try:
            if url.path in STATIC:
                path, kind = STATIC[url.path]
                self.send(path.read_bytes(), kind)
            elif url.path == "/api/areas":
                self.send(json.dumps(areas()).encode(), "application/json")
            elif url.path in SOURCE_TABLES:
                table = source_table(ROOT / "data" / SOURCE_TABLES[url.path])
                self.send(json.dumps(table).encode(), "application/json")
            elif url.path == "/api/responses":
                self.send(json.dumps(responses()).encode(), "application/json")
            elif url.path == "/student-responses.md":
                self.send(
                    response_download().encode("utf-8"),
                    "text/markdown; charset=utf-8",
                    download="student-responses.md",
                )
            elif url.path == "/notes.md":
                self.send(
                    (ROOT / "work" / "notes.md").read_bytes(),
                    "text/markdown; charset=utf-8",
                    download="notes.md",
                )
            elif match := FIGURE_PATH.fullmatch(url.path):
                extension = match[1]
                self.send(
                    (ROOT / "work" / url.path[1:]).read_bytes(),
                    FIGURE_TYPES[extension],
                    policy=FIGURE_POLICIES.get(extension),
                )
            elif url.path == "/api/live":
                self.send(json.dumps(live()).encode(), "application/json")
            else:
                self.send(b"Not found", "text/plain", 404)
        except FileNotFoundError:
            self.send(b"Not found", "text/plain", 404)
        except OSError:
            self.send(b"Could not read the workspace", "text/plain", 500)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/responses":
            self.send(b"Not found", "text/plain", 404)
            return
        if self.headers.get_content_type() != "application/json":
            self.send(b"Expected JSON", "text/plain", 415)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_RESPONSE_BODY:
                self.send(b"Invalid response length", "text/plain", 413)
                return
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise TypeError("Expected a response object")
            key, answer = payload.get("step"), payload.get("answer")
            if not isinstance(key, str) or key not in RESPONSE_STEPS:
                raise ValueError("Unknown prompt")
            if (
                not isinstance(answer, str)
                or "\0" in answer
                or len(answer) > MAX_RESPONSE
            ):
                raise ValueError("Invalid answer text")
            answer = answer.replace("\r\n", "\n").replace("\r", "\n").strip()
            save_response(key, answer)
        except TypeError, ValueError:
            self.send(b"Invalid response", "text/plain", 400)
        except OSError:
            self.send(b"Could not save the response", "text/plain", 500)

        else:
            self.send(json.dumps({"answer": answer}).encode(), "application/json")

    def log_message(self, format: str, *args: Any) -> None:
        pass


def bind(host: str, port: int, tries: int = 10) -> ThreadingHTTPServer:
    """Listen on the first free port from `port` onward."""
    for candidate in range(port, port + tries):
        try:
            return ThreadingHTTPServer((host, candidate), Handler)
        except OSError as exc:
            if exc.errno != errno.EADDRINUSE:
                raise
    raise OSError(f"Ports {port} to {port + tries - 1} are all in use; try --port")


def serve(host: str, port: int) -> None:
    """Serve the viewer, printing the address actually used."""
    server = bind(host, port)
    used = server.server_address[1]
    if port and used != port:
        print(f"Port {port} is in use, so the viewer uses {used} instead.")
    print(f"Lesson viewer: http://{host}:{used}/  (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
