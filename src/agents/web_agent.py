"""
src/agents/web_agent.py
────────────────────────
Web Agent — owns the Search Tool only.
Exposes call_web_agent as the orchestrator-facing @tool.
"""

from __future__ import annotations

from langchain_core.tools import tool

from src.helpers.search import single_search

@tool
def search_tool(query: str) -> str:
    """Search the web and return raw results."""
    result = single_search(query)
    return f"## Search results for: \"{query}\"\n\n{result.raw}"

class WebAgent:
    TOOLS = [search_tool]

    def search(self, query: str) -> str:
        return search_tool.invoke({"query": query})

_instance = None

def _get() -> WebAgent:
    global _instance
    if _instance is None:
        _instance = WebAgent()
    return _instance

@tool
def call_web_agent(query: str) -> str:
    """
    Call the Web Agent to search the internet for current information.
    Use one focused query per call. Call multiple times for different angles.

    Args:
        query: A specific focused search query (5-8 words).
    """
    print(f"\n  [Web Agent]  searching: {query}")
    return _get().search(query)
