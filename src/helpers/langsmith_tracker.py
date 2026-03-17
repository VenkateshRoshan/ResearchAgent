"""
src/helpers/langsmith_tracker.py
──────────────────────────────────
LangSmith tracing utilities.

LangChain auto-traces when these env vars are set (handled by config.py):
  LANGCHAIN_TRACING_V2=true
  LANGCHAIN_API_KEY=...
  LANGCHAIN_PROJECT=...

This module adds:
  - setup_tracing()     : validate config and print status
  - trace_run()         : context manager that wraps a block in a named run
  - get_run_url()       : return the LangSmith URL for the current run (if any)
  - ResearchRunMetadata : dataclass for attaching structured metadata to runs
"""

from __future__ import annotations

import functools
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Generator, Optional

from config import cfg


# ── Metadata dataclass ─────────────────────────────────────────────────────────

@dataclass
class ResearchRunMetadata:
    """Structured metadata attached to every LangSmith run."""
    topic:      str
    model:      str   = cfg.OLLAMA_MODEL
    timestamp:  str   = field(default_factory=lambda: datetime.utcnow().isoformat())
    tags:       list  = field(default_factory=lambda: ["research", "react", "ollama"])
    extra:      dict  = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Setup ──────────────────────────────────────────────────────────────────────

def setup_tracing() -> bool:
    """
    Validate LangSmith configuration and print a status banner.

    Returns:
        True if tracing is active, False if disabled or misconfigured.
    """
    if not cfg.is_langsmith_enabled():
        print("[LangSmith] Tracing DISABLED.")
        print("            To enable: set LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY in .env")
        return False

    try:
        from langsmith import Client
        client = Client(api_key=cfg.LANGCHAIN_API_KEY, api_url=cfg.LANGCHAIN_ENDPOINT)
        # Light check — list projects to confirm connectivity
        _ = list(client.list_projects())
        print(f"[LangSmith] Tracing ACTIVE")
        print(f"            Project : {cfg.LANGCHAIN_PROJECT}")
        print(f"            View at : https://smith.langchain.com/projects")
        return True
    except Exception as e:
        print(f"[LangSmith] WARNING — Could not connect: {e}")
        print("            Runs will still be traced if env vars are set, but connectivity check failed.")
        return False


# ── Context manager ────────────────────────────────────────────────────────────

@contextmanager
def trace_run(
    name: str,
    metadata: Optional[ResearchRunMetadata] = None,
    tags: Optional[list[str]] = None,
) -> Generator[Any, None, None]:
    """
    Context manager that wraps a block in a named LangSmith run.
    If LangSmith is disabled, it's a no-op.

    Usage:
        with trace_run("research_phase", metadata=meta) as run:
            result = agent.invoke(...)

    Args:
        name:     Human-readable run name shown in LangSmith UI.
        metadata: ResearchRunMetadata instance with topic, model, etc.
        tags:     Extra tags beyond those in metadata.
    """
    if not cfg.is_langsmith_enabled():
        yield None
        return

    try:
        from langsmith import trace
        all_tags  = (metadata.tags if metadata else []) + (tags or [])
        meta_dict = metadata.to_dict() if metadata else {}

        with trace(name=name, metadata=meta_dict, tags=all_tags) as run_tree:
            yield run_tree

    except ImportError:
        # langsmith package not installed — degrade gracefully
        print("[LangSmith] 'langsmith' package not found. pip install langsmith")
        yield None
    except Exception as e:
        print(f"[LangSmith] trace_run error: {e}")
        yield None


# ── Run URL helper ─────────────────────────────────────────────────────────────

def get_run_url(run_id: Optional[str] = None) -> Optional[str]:
    """
    Return the LangSmith URL for a run ID (or the current run if inside trace_run).
    Returns None if tracing is not enabled.
    """
    if not cfg.is_langsmith_enabled() or not run_id:
        return None
    project = cfg.LANGCHAIN_PROJECT.replace(" ", "-")
    return f"https://smith.langchain.com/projects/{project}/runs/{run_id}"


# ── Decorator for tracing individual functions ─────────────────────────────────

def traced(run_name: Optional[str] = None, tags: Optional[list[str]] = None):
    """
    Decorator to auto-trace a function call in LangSmith.

    Usage:
        @traced("verify_report", tags=["verifier"])
        def verify(report: str) -> str:
            ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            name = run_name or fn.__name__
            with trace_run(name, tags=tags):
                return fn(*args, **kwargs)
        return wrapper
    return decorator