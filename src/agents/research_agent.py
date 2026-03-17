"""
src/agents/research_agent.py
─────────────────────────────
Research Agent — owns Research Tool only.
Synthesises raw search results. Does NOT search the web.
Exposes call_research_agent as the orchestrator-facing @tool.
"""

from __future__ import annotations

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage

from config import get_llm
from src.helpers.prompts import research_agent_prompt


# ── Internal tool ──────────────────────────────────────────────────────────────

@tool
def research_tool(topic: str, raw_search_results: str) -> str:
    """Synthesise raw search results into a structured research report."""
    messages = [
        SystemMessage(content=research_agent_prompt()),
        HumanMessage(content=f"Topic: {topic}\n\nRaw results:\n{raw_search_results}"),
    ]
    return get_llm().invoke(messages).content


# ── Agent class ────────────────────────────────────────────────────────────────

class ResearchAgent:
    TOOLS = [research_tool]

    def synthesise(self, topic: str, raw_search_results: str) -> str:
        return research_tool.invoke({"topic": topic, "raw_search_results": raw_search_results})


# ── Orchestrator-facing tool ───────────────────────────────────────────────────

_instance = None

def _get() -> ResearchAgent:
    global _instance
    if _instance is None:
        _instance = ResearchAgent()
    return _instance

@tool
def call_research_agent(topic: str, raw_search_results: str) -> str:
    """
    Call the Research Agent to synthesise raw search results into a report.
    This agent does NOT search — only processes what you give it.

    Args:
        topic:              The main research topic.
        raw_search_results: All raw search results collected so far combined.
    """
    print(f"\n  [Research Agent]  synthesising: {topic}")
    return _get().synthesise(topic=topic, raw_search_results=raw_search_results)
