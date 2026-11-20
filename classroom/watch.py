"""Forward saved student responses to a Codex thread or a Claude monitor."""

import json
import os
import re
import subprocess
from contextlib import nullcontext
from pathlib import Path
from time import monotonic, sleep
from typing import Any

from ui.server import RESPONSE_STEPS, ROOT, responses, table_reply_path


class CodexThread:
    def __init__(self, connection: Any) -> None:
        self.connection = connection
        self.request_id = 0
        self.call(
            "initialize",
            {"clientInfo": {"name": "lesson-response-watcher", "version": "0.1.0"}},
        )
        self.connection.send(json.dumps({"method": "initialized"}))

    def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.request_id += 1
        self.connection.send(
            json.dumps({"id": self.request_id, "method": method, "params": params})
        )
        deadline = monotonic() + 15
        while monotonic() < deadline:
            message = json.loads(
                self.connection.recv(timeout=max(0, deadline - monotonic()))
            )
            if message.get("id") != self.request_id:
                continue
            if "result" in message:
                return message["result"]
            if "error" in message:
                raise ValueError(
                    f"Codex rejected {method}. Check the conversation and watcher setup."
                )
        raise TimeoutError(f"Codex did not reply to {method}.")

    def attach(self, thread: str | None) -> str:
        if not thread:
            return self.call(
                "thread/start",
                {
                    "cwd": str(ROOT),
                    "approvalPolicy": "never",
                    "sandbox": "workspace-write",
                },
            )["thread"]["id"]
        details = self.call("thread/read", {"threadId": thread, "includeTurns": False})[
            "thread"
        ]
        if Path(details["cwd"]).resolve() != ROOT.resolve():
            raise ValueError("The Codex conversation belongs to a different workspace.")
        return thread

    def status(self, thread: str) -> str:
        details = self.call("thread/read", {"threadId": thread, "includeTurns": False})[
            "thread"
        ]
        return details["status"]["type"]

    def send(self, thread: str, prompt: str, status: str) -> str:
        if status == "notLoaded":
            self.call("thread/resume", {"threadId": thread})
        result = self.call(
            "turn/start",
            {
                "threadId": thread,
                "input": [{"type": "text", "text": prompt, "text_elements": []}],
            },
        )
        return result["turn"]["id"]

    def final_reply(self, thread: str, turn_id: str) -> str:
        turns = self.call("thread/read", {"threadId": thread, "includeTurns": True})["thread"]["turns"]
        for turn in turns:
            if turn["id"] == turn_id:
                return next((item["text"] for item in reversed(turn["items"])
                             if item.get("type") == "agentMessage" and item.get("phase") == "final_answer"), "")
        return ""


def codex_socket() -> str:
    try:
        result = subprocess.run(
            ["codex", "app-server", "daemon", "version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(
            "Start a signed-in Codex session with its App Server running first."
        ) from exc
    status = json.loads(result.stdout)
    if status.get("status") != "running" or not status.get("socketPath"):
        raise ValueError(
            "Start the Codex App Server before running the response watcher."
        )
    return status["socketPath"]


def student_message(step: str, answer: str) -> str:
    phase, prompt = RESPONSE_STEPS[step]
    action = prompt.get("prompt") or (
        "Give brief feedback on this answer. Stay on this prompt and wait for the student's "
        "response to a later action prompt before doing that later work."
    )
    if prompt.get("source"):
        path = table_reply_path(step, answer)
        action = (
            "Answer the @agent note in the lesson viewer. Create the parent directory "
            f"and write your brief student-facing reply as plain text to {path}. "
            "Do this before acknowledging the request in chat. Leave the next lesson "
            "decision to the student."
        )
    hint = (
        f"\nAnswer guidance in the viewer: {prompt['hint']}"
        if prompt.get("hint")
        else ""
    )
    missing_details = (
        "Fill in missing details with reasonable assumptions and continue. "
        if prompt.get("fillMissingDetails")
        else "If a detail needed for the next action is missing, name it and wait for a "
        "revision in the viewer. "
    )
    return (
        "The students saved an answer in the Michigan EV charging lesson viewer. "
        "Read AGENTS.md and classroom/SESSION.md, and use the saved responses as context. "
        "All student-facing questions belong in the viewer. Use chat for acknowledgments, "
        "answers, and results. Point to a viewer prompt if more input is needed. "
        "Check the content against the prompt before acting. A short, specific answer is "
        f"enough. {missing_details}"
        "Where the answer supports useful work, state any assumption "
        "you make. Leave the student's reasoning to them. "
        "This is their current step. Leave the answer files to the students.\n\n"
        f"{phase} → {prompt['label']}\n{prompt['response']}{hint}\n\n"
        f"Student answer:\n{answer}\n\n"
        f"Action for this step: {action}"
    )


def collect_changes(
    previous: dict[str, str], current: dict[str, str], pending: dict[str, str]
) -> None:
    for step in list(pending):
        if step not in current:
            del pending[step]
    for step, answer in current.items():
        if previous.get(step) == answer:
            continue
        if RESPONSE_STEPS[step][1].get("source") and not re.match(
            r"^@agent[\s,:]+[^\s,:]", answer.strip(), re.IGNORECASE
        ):
            pending.pop(step, None)
        else:
            pending[step] = answer


def watch(thread: str | None, events: bool) -> None:
    from fcntl import LOCK_EX, LOCK_NB, flock

    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with (work / ".response-watcher.lock").open("a", encoding="utf-8") as lock:
        try:
            flock(lock, LOCK_EX | LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError(
                "A response watcher is already running for this workspace."
            ) from exc
        previous = responses()
        pending: dict[str, str] = {}
        context = nullcontext()
        if not events:
            from websockets.sync.client import unix_connect

            context = unix_connect(codex_socket(), open_timeout=5)
        with context as connection:
            agent = None
            if connection is not None:
                agent = CodexThread(connection)
                thread = agent.attach(thread or os.environ.get("CODEX_THREAD_ID"))
                print(
                    f"Watching work/responses/ for Codex thread {thread}.", flush=True
                )
            activity = work / ".agent-active"
            submitted = None
            try:
                while True:
                    current = responses()
                    collect_changes(previous, current, pending)
                    previous = current
                    status = agent.status(thread) if agent and thread else "unknown"
                    if submitted and agent and thread and status != "active":
                        step, answer, turn_id = submitted
                        reply = agent.final_reply(thread, turn_id)
                        path = ROOT / table_reply_path(step, answer)
                        if reply and not path.exists():
                            path.parent.mkdir(parents=True, exist_ok=True)
                            path.write_text(reply, encoding="utf-8")
                        submitted = None
                    if pending:
                        step, answer = next(iter(pending.items()))
                        message = student_message(step, answer)
                        if agent is None:
                            print(
                                json.dumps(
                                    {"step": step, "message": message},
                                    ensure_ascii=False,
                                ),
                                flush=True,
                            )
                            del pending[step]
                        elif thread and status != "active":
                            turn_id = agent.send(thread, message, status)
                            submitted = (step, answer, turn_id)
                            status = "active"
                            print(f"Submitted {step} to Codex.", flush=True)
                            del pending[step]
                    if status == "active":
                        activity.touch()
                    elif activity.exists():
                        activity.unlink()
                    sleep(1)
            finally:
                activity.unlink(missing_ok=True)
