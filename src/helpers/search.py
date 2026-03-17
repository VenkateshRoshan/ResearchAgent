"""
src/helpers/search.py
──────────────────────
Web search utilities used by the research agent.

Features:
  - multi_search()  : fire several queries, deduplicate, return merged results
  - format_results(): clean markdown formatting for LLM consumption
  - DuckDuckGo backend (no API key needed)
"""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import List

from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool

from config import cfg

_ddg = DuckDuckGoSearchRun()

@dataclass
class SearchResult:
    query: str
    raw:   str
    uid:   str = field(init=False)

    def __post_init__(self):
        # Deterministic fingerprint — lets us deduplicate near-identical results
        self.uid = hashlib.md5(self.raw[:200].encode()).hexdigest()

def single_search(query: str) -> SearchResult:
    """Run one DuckDuckGo query and return a SearchResult."""
    raw = _ddg.run(query)
    return SearchResult(query=query, raw=raw)

def multi_search(queries: List[str]) -> List[SearchResult]:
    """
    Run multiple queries, deduplicate results by content fingerprint,
    and return a list of unique SearchResult objects.

    Args:
        queries: List of search query strings.

    Returns:
        Deduplicated list of SearchResult (capped at cfg.MAX_SEARCH_RESULTS).
    """
    seen:    set[str]          = set()
    results: List[SearchResult] = []

    capped_queries = queries[: cfg.MAX_SEARCH_RESULTS]

    with ThreadPoolExecutor(max_workers=min(3, len(capped_queries) or 1)) as executor:
        search_results = list(executor.map(single_search, capped_queries))

    for sr in search_results:
        if sr.uid not in seen:
            seen.add(sr.uid)
            results.append(sr)

    return results


def format_results(results: List[SearchResult]) -> str:
    """
    Convert a list of SearchResult objects into clean Markdown
    suitable for injection into an LLM prompt.
    """
    if not results:
        return "No search results found."

    sections = []
    for i, sr in enumerate(results, 1):
        sections.append(
            f"### Source {i} — query: \"{sr.query}\"\n"
            f"{sr.raw.strip()}\n"
        )

    return "\n---\n".join(sections)


@tool
def web_search(query: str) -> str:
    """
    Search the web for current information on a topic.
    Use a concise, specific query (5-8 words).
    Returns a snippet of the most relevant results.

    Args:
        query: The search query string.
    """
    sr = single_search(query)
    return f"Results for '{query}':\n\n{sr.raw}"


@tool
def multi_web_search(queries_csv: str) -> str:
    """
    Run multiple web searches at once and return merged, deduplicated results.
    Use this when you need to cover several angles of a topic simultaneously.

    Args:
        queries_csv: Comma-separated list of search queries.
                     Example: "AI agents 2025, LangGraph tutorial, ReAct paper"
    """
    queries = [q.strip() for q in queries_csv.split(",") if q.strip()]
    results = multi_search(queries)
    return format_results(results)
