"""
src/agents/verifier_agent.py
─────────────────────────────
Verifier Agent — owns Verifier Tool only.
Fact-checks a report and returns verdict + follow-up queries.
Exposes call_verifier_agent as the orchestrator-facing @tool.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage

from config import get_llm
from src.helpers.prompts import verifier_agent_prompt


# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass
class VerificationResult:
    topic:             str
    verdict:           str
    full_assessment:   str
    follow_up_queries: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.verdict == "PASS"


def _parse_verdict(text: str) -> str:
    upper = text.upper()
    for kw in ("PASS", "FAIL", "NEEDS WORK"):
        if kw in upper:
            return kw
    return "UNKNOWN"


def _parse_follow_ups(text: str) -> List[str]:
    match = re.search(
        r"recommended follow.up searches?\s*\n(.*?)(?:\n##|\Z)",
        text, re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return []
    return [
        line.strip().lstrip("-*•").strip()
        for line in match.group(1).splitlines()
        if line.strip().lstrip("-*•").strip()
    ][:5]


# ── Internal tool ──────────────────────────────────────────────────────────────

@tool
def verifier_tool(topic: str, report: str) -> str:
    """Fact-check a research report and return structured assessment."""
    messages = [
        SystemMessage(content=verifier_agent_prompt()),
        HumanMessage(content=f"Topic: {topic}\n\nReport:\n{report}"),
    ]
    return get_llm().invoke(messages).content


# ── Agent class ────────────────────────────────────────────────────────────────

class VerifierAgent:
    TOOLS = [verifier_tool]

    def verify(self, topic: str, report: str) -> VerificationResult:
        assessment = verifier_tool.invoke({"topic": topic, "report": report})
        return VerificationResult(
            topic=topic,
            verdict=_parse_verdict(assessment),
            full_assessment=assessment,
            follow_up_queries=_parse_follow_ups(assessment),
        )


# ── Orchestrator-facing tool ───────────────────────────────────────────────────

_instance = None

def _get() -> VerifierAgent:
    global _instance
    if _instance is None:
        _instance = VerifierAgent()
    return _instance

@tool
def call_verifier_agent(topic: str, report: str) -> str:
    """
    Call the Verifier Agent to fact-check a research report.
    Returns claim audit, gap analysis, verdict (PASS/NEEDS WORK/FAIL), follow-up queries.

    Args:
        topic:  The original research topic.
        report: The full report text from call_research_agent.
    """
    print(f"\n  [Verifier Agent]  verifying: {topic}")
    return _get().verify(topic=topic, report=report).full_assessment
