"""
src/agents/architecture_agent.py
──────────────────────────────────
Architecture Agent — owns Draw Tool and Update Tool.
Produces and updates Mermaid diagrams.
Exposes call_architecture_agent as the orchestrator-facing @tool.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage

from config import get_llm
from src.helpers.prompts import architecture_agent_prompt

DIAGRAMS_DIR = Path("memory/diagrams")


def _ensure_dir():
    DIAGRAMS_DIR.mkdir(parents=True, exist_ok=True)


# ── Internal tools ─────────────────────────────────────────────────────────────

@tool
def draw_tool(topic: str, description: str) -> str:
    """Generate a new Mermaid diagram and save to memory/diagrams/<topic>.md."""
    messages = [
        SystemMessage(content=architecture_agent_prompt()),
        HumanMessage(content=f"Draw architecture for: {topic}\n\n{description}"),
    ]
    diagram = get_llm().invoke(messages).content
    _ensure_dir()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    (DIAGRAMS_DIR / f"{topic}.md").write_text(
        f"# Architecture: {topic}\n_Generated: {ts}_\n\n{diagram}\n", encoding="utf-8"
    )
    return f"Saved to memory/diagrams/{topic}.md\n\n{diagram}"


@tool
def update_tool(topic: str, updates: str) -> str:
    """Update an existing diagram with new information."""
    _ensure_dir()
    path = DIAGRAMS_DIR / f"{topic}.md"
    if not path.exists():
        return f"No diagram found for '{topic}'. Use draw_tool first."
    existing = path.read_text(encoding="utf-8")
    messages = [
        SystemMessage(content=architecture_agent_prompt()),
        HumanMessage(content=f"Update diagram for: {topic}\n\nExisting:\n{existing}\n\nUpdates:\n{updates}"),
    ]
    updated = get_llm().invoke(messages).content
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    path.write_text(
        f"# Architecture: {topic}\n_Updated: {ts}_\n\n{updated}\n", encoding="utf-8"
    )
    return f"Updated memory/diagrams/{topic}.md\n\n{updated}"


# ── Agent class ────────────────────────────────────────────────────────────────

class ArchitectureAgent:
    TOOLS = [draw_tool, update_tool]

    def draw(self, topic: str, description: str) -> str:
        return draw_tool.invoke({"topic": topic, "description": description})

    def update(self, topic: str, updates: str) -> str:
        return update_tool.invoke({"topic": topic, "updates": updates})

    def list_diagrams(self) -> list[str]:
        _ensure_dir()
        return [p.stem for p in sorted(DIAGRAMS_DIR.glob("*.md"))]


# ── Orchestrator-facing tool ───────────────────────────────────────────────────

_instance = None

def _get() -> ArchitectureAgent:
    global _instance
    if _instance is None:
        _instance = ArchitectureAgent()
    return _instance

@tool
def call_architecture_agent(action: str, topic: str, content: str) -> str:
    """
    Call the Architecture Agent to draw or update a system diagram.

    Actions:
      draw   — create a new Mermaid diagram (requires: topic, content=description)
      update — update an existing diagram   (requires: topic, content=update notes)

    Args:
        action:  'draw' or 'update'
        topic:   Short diagram slug e.g. 'bci_eeg_pipeline'
        content: System description or update notes
    """
    print(f"\n  [Architecture Agent]  action={action} topic={topic}")
    if action == "draw":
        return _get().draw(topic=topic, description=content)
    elif action == "update":
        return _get().update(topic=topic, updates=content)
    return f"Unknown action '{action}'. Use 'draw' or 'update'."
