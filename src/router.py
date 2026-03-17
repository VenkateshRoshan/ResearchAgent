"""
src/router.py
──────────────
Router — validates, dispatches, then forces memory save.

After every run:
  1. LLM generates a short filename + 1-2 line description
  2. Report saved to memory/<llm_filename>.md
  3. topics.md updated with: <filename>.md -> <description>
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from config import get_llm
from src.helpers.langsmith_tracker import trace_run, ResearchRunMetadata
from src.orchestrator import Orchestrator
from memory_manager import save_to_topic_file, update_memory_index, log_session, MEMORY_DIR


@dataclass
class RouteResult:
    query:       str
    answer:      str
    elapsed_sec: float
    filename:    str = ""
    run_id:      Optional[str] = None
    error:       Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None

    def display(self) -> str:
        lines = [
            f"\n{'=' * 66}",
            f"  RESULT  —  {self.query}",
            f"{'=' * 66}",
            self.answer,
            f"\n{'─' * 66}",
            f"  Time elapsed : {self.elapsed_sec:.1f}s",
            f"  Saved to     : memory/{self.filename}.md",
            f"  Index        : memory/topics.md",
        ]
        if self.error:
            lines.append(f"  Error        : {self.error}")
        lines.append(f"{'─' * 66}\n")
        return "\n".join(lines)

def _llm_generate_filename_and_desc(query: str, answer: str) -> tuple[str, str]:
    """
    Ask the LLM to generate:
      - a short snake_case filename (no .md, no spaces)
      - a 1-2 line description of what the file contains

    Returns: (filename, description)
    """
    messages = [
        SystemMessage(content=(
            "You generate filenames and descriptions for research files.\n"
            "Reply in EXACTLY this format, nothing else:\n"
            "FILENAME: <snake_case_name_no_extension>\n"
            "DESCRIPTION: <1-2 sentence description of what this file contains>\n\n"
            "Rules:\n"
            "- Filename: lowercase, underscores only, max 30 chars, no .md\n"
            "- Description: 1-2 sentences, start with 'This file contains...'\n"
            "- No extra text, no explanation, just the two lines above."
        )),
        HumanMessage(content=(
            f"Research query: {query}\n\n"
            f"Report preview (first 300 chars):\n{answer[:300]}"
        )),
    ]

    try:
        response = get_llm().invoke(messages)
        text = response.content.strip()

        filename    = "research"
        description = "Research notes."

        for line in text.splitlines():
            if line.upper().startswith("FILENAME:"):
                raw = line.split(":", 1)[1].strip()
                # Sanitise just in case the LLM adds spaces or dots
                filename = re.sub(r"[^a-z0-9_]", "_", raw.lower()).strip("_")[:40] or "research"
            elif line.upper().startswith("DESCRIPTION:"):
                description = line.split(":", 1)[1].strip()

        return filename, description

    except Exception as e:
        return "research", f"Research on: {query[:60]}"

def _update_topics_index(filename: str, description: str) -> None:
    """
    Append or update an entry in memory/topics.md:
      BCI.md -> This file contains ...
    """
    topics_path = MEMORY_DIR / "topics.md"

    if not topics_path.exists():
        topics_path.write_text(
            "# topics.md — Research File Index\n"
            "_Auto-updated after every session._\n\n",
            encoding="utf-8",
        )

    current = topics_path.read_text(encoding="utf-8")
    entry   = f"{filename}.md -> {description}\n"

    # Replace existing entry for same filename, or append
    if f"{filename}.md ->" in current:
        lines = current.splitlines()
        lines = [entry.rstrip() if l.startswith(f"{filename}.md ->") else l for l in lines]
        topics_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        topics_path.write_text(current + entry, encoding="utf-8")

class Router:

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self._orchestrator: Optional[Orchestrator] = None

    def _get_orchestrator(self) -> Orchestrator:
        if self._orchestrator is None:
            self._orchestrator = Orchestrator()
        return self._orchestrator

    def _force_save(self, query: str, answer: str) -> str:
        """
        Always save after every run. LLM decides filename + description.
        Returns the filename used.
        """
        try:
            if self.verbose:
                print(f"\n[Router]  Generating filename via LLM...")

            filename, description = _llm_generate_filename_and_desc(query, answer)

            if self.verbose:
                print(f"[Router]  Saving → memory/{filename}.md")
                print(f"[Router]  Desc   → {description}")

            # Save the report
            save_to_topic_file(filename, answer, append=False)

            # Update topics.md index
            _update_topics_index(filename, description)

            # Update MEMORY.md index pointer
            update_memory_index(f"`{filename}.md` — {description}")

            # Log session
            log_session(
                f"Query  : {query[:120]}\n"
                f"Saved  : memory/{filename}.md\n"
                f"Desc   : {description}"
            )

            return filename

        except Exception as e:
            if self.verbose:
                print(f"\n[Router]  WARNING: memory save failed: {e}")
            return "research"

    def route(self, query: str) -> RouteResult:
        query = query.strip()

        if not query:
            return RouteResult(query=query, answer="", elapsed_sec=0,
                               error="Empty query.")
        
        if self.verbose:
            print(f"\n[Router]  /query → \"{query}\"")

        meta   = ResearchRunMetadata(topic=query, tags=["router", "research-pipeline"])
        start  = time.time()
        answer = ""
        error  = None
        run_id = None

        try:
            with trace_run(f"route: {query}", metadata=meta) as run:
                answer = self._get_orchestrator().run(query, verbose=self.verbose)
                run_id = getattr(run, "id", None)
        except Exception as e:
            error = str(e)
            if self.verbose:
                print(f"[Router]  ERROR: {e}")

        filename = ""
        if answer:
            filename = self._force_save(query, answer)

        elapsed = round(time.time() - start, 1)

        return RouteResult(
            query=query,
            answer=answer,
            elapsed_sec=elapsed,
            filename=filename,
            run_id=run_id,
            error=error,
        )
