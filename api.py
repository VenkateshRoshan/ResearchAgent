"""
api.py
──────
Small HTTP API that bridges the browser UI to the existing research pipeline.

Endpoints:
  GET  /health
  POST /chat/start          {"query": "..."}
  GET  /stream/<job_id>     Server-Sent Events stream
  GET  /jobs/<job_id>       Current job snapshot

This file intentionally reuses the existing `Router` / `Orchestrator` pipeline
without changing the rest of the codebase.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from memory_manager import bootstrap_memory_dir
from src.helpers.langsmith_tracker import setup_tracing
from src.router import Router


@dataclass
class JobState:
    job_id: str
    query: str
    created_at: float = field(default_factory=time.time)
    events: list[dict[str, Any]] = field(default_factory=list)
    done: bool = False
    error: str | None = None
    answer: str = ""
    filename: str = ""
    elapsed_sec: float = 0.0
    next_event_id: int = 1
    condition: threading.Condition = field(default_factory=threading.Condition)

    def add_event(self, event_type: str, **payload: Any) -> dict[str, Any]:
        with self.condition:
            event = {
                "id": self.next_event_id,
                "type": event_type,
                "ts": time.time(),
                **payload,
            }
            self.next_event_id += 1
            self.events.append(event)
            self.condition.notify_all()
            return event

    def mark_done(self) -> None:
        with self.condition:
            self.done = True
            self.condition.notify_all()

    def snapshot(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "query": self.query,
            "created_at": self.created_at,
            "done": self.done,
            "error": self.error,
            "answer": self.answer,
            "filename": self.filename,
            "elapsed_sec": self.elapsed_sec,
            "events": self.events,
        }


JOBS: dict[str, JobState] = {}
JOBS_LOCK = threading.Lock()


def _friendly_agent_name(agent: str) -> str:
    return {
        "call_web_agent": "Web Agent",
        "call_memory_agent": "Memory Agent",
        "call_research_agent": "Research Agent",
        "call_verifier_agent": "Verifier Agent",
        "call_architecture_agent": "Architecture Agent",
    }.get(agent, agent.replace("_", " ").title())


def _compact_json(value: Any, limit: int = 220) -> str:
    text = json.dumps(value, ensure_ascii=False)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _run_pipeline_job(job: JobState) -> None:
    started = time.time()
    router = Router(verbose=False)

    try:
        query = job.query.strip()
        if not query:
            raise ValueError("Query cannot be empty.")
        if len(query) < 3:
            raise ValueError("Query too short — be more specific.")

        job.add_event(
            "status",
            label="Starting research pipeline",
            detail="The orchestrator is planning the first steps.",
        )

        final_answer = ""
        orchestrator = router._get_orchestrator()

        for item in orchestrator.stream(query):
            event_type = item.get("type")

            if event_type == "action":
                agent = str(item.get("agent", "agent"))
                args = item.get("args", {})
                job.add_event(
                    "thinking",
                    step=item.get("step", 0),
                    phase="action",
                    agent=agent,
                    agent_label=_friendly_agent_name(agent),
                    summary=f"Calling {_friendly_agent_name(agent)} with {_compact_json(args)}",
                    args=args,
                )
            elif event_type == "observation":
                agent = str(item.get("agent", "agent"))
                content = str(item.get("content", ""))
                preview = content.strip().replace("\n", " ")
                if len(preview) > 320:
                    preview = preview[:319] + "…"
                job.add_event(
                    "thinking",
                    step=item.get("step", 0),
                    phase="observation",
                    agent=agent,
                    agent_label=_friendly_agent_name(agent),
                    summary=f"{_friendly_agent_name(agent)} returned an observation.",
                    preview=preview,
                    content=content,
                )
            elif event_type == "final":
                final_answer = str(item.get("content", ""))
                job.answer = final_answer
                job.add_event(
                    "final",
                    content=final_answer,
                )

        if not final_answer:
            raise RuntimeError("The orchestrator finished without a final answer.")

        job.add_event(
            "status",
            label="Saving final markdown",
            detail="Persisting the report into the memory folder.",
        )
        job.filename = router._force_save(query, final_answer)
        job.elapsed_sec = round(time.time() - started, 1)
        job.add_event(
            "done",
            elapsed_sec=job.elapsed_sec,
            filename=job.filename,
            saved_to=f"memory/{job.filename}.md" if job.filename else "",
        )
    except Exception as exc:  # pragma: no cover - defensive server path
        job.error = str(exc)
        job.elapsed_sec = round(time.time() - started, 1)
        job.add_event(
            "error",
            message=job.error,
            elapsed_sec=job.elapsed_sec,
        )
    finally:
        job.mark_done()


class ResearchAPIHandler(BaseHTTPRequestHandler):
    server_version = "ResearchAgentAPI/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _set_headers(
        self,
        status: HTTPStatus = HTTPStatus.OK,
        content_type: str = "application/json; charset=utf-8",
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _write_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        self._set_headers(status=status)
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self) -> None:
        self._set_headers(status=HTTPStatus.NO_CONTENT)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/health":
            self._write_json({"ok": True, "jobs": len(JOBS)})
            return

        if path == "/":
            self._write_json(
                {
                    "name": "myResearchAgent API",
                    "health": "/health",
                    "start": "/chat/start",
                    "stream": "/stream/<job_id>",
                    "job": "/jobs/<job_id>",
                }
            )
            return

        if path.startswith("/jobs/"):
            job_id = path.split("/jobs/", 1)[1]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if not job:
                self._write_json({"error": "Job not found."}, status=HTTPStatus.NOT_FOUND)
                return
            self._write_json(job.snapshot())
            return

        if path.startswith("/stream/"):
            job_id = path.split("/stream/", 1)[1]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if not job:
                self._write_json({"error": "Job not found."}, status=HTTPStatus.NOT_FOUND)
                return
            self._stream_job(job)
            return

        self._write_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path != "/chat/start":
            self._write_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            body = self._read_json_body()
        except json.JSONDecodeError:
            self._write_json({"error": "Invalid JSON body."}, status=HTTPStatus.BAD_REQUEST)
            return

        query = str(body.get("query", "")).strip()
        if not query:
            self._write_json({"error": "'query' is required."}, status=HTTPStatus.BAD_REQUEST)
            return

        job = JobState(job_id=uuid.uuid4().hex, query=query)
        with JOBS_LOCK:
            JOBS[job.job_id] = job

        thread = threading.Thread(target=_run_pipeline_job, args=(job,), daemon=True)
        thread.start()

        host, port = self.server.server_address[:2]
        self._write_json(
            {
                "job_id": job.job_id,
                "query": query,
                "stream_url": f"http://{host}:{port}/stream/{job.job_id}",
                "job_url": f"http://{host}:{port}/jobs/{job.job_id}",
            },
            status=HTTPStatus.ACCEPTED,
        )

    def _stream_job(self, job: JobState) -> None:
        self._set_headers(
            content_type="text/event-stream; charset=utf-8",
            extra_headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

        last_event_id = 0

        try:
            while True:
                to_send: list[dict[str, Any]] = []
                with job.condition:
                    if len(job.events) > last_event_id:
                        to_send = job.events[last_event_id:]
                    elif job.done:
                        break
                    else:
                        job.condition.wait(timeout=15)
                        if len(job.events) > last_event_id:
                            to_send = job.events[last_event_id:]
                        elif job.done:
                            break
                        else:
                            self.wfile.write(b": keep-alive\n\n")
                            self.wfile.flush()
                            continue

                for event in to_send:
                    payload = json.dumps(event, ensure_ascii=False)
                    chunk = (
                        f"id: {event['id']}\n"
                        f"event: {event['type']}\n"
                        f"data: {payload}\n\n"
                    ).encode("utf-8")
                    self.wfile.write(chunk)
                    self.wfile.flush()
                    last_event_id = int(event["id"])

                if job.done and last_event_id >= len(job.events):
                    break
        except (BrokenPipeError, ConnectionResetError):
            return


def build_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), ResearchAPIHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the myResearchAgent HTTP API.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    args = parser.parse_args()

    setup_tracing()
    bootstrap_memory_dir()

    server = build_server(args.host, args.port)
    print(f"API running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down API...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
