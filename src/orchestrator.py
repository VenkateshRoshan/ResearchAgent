"""
src/orchestrator.py
────────────────────
The Orchestrator — the ONLY place where reasoning happens.

No @tool definitions here. Each agent owns its own tool.
The orchestrator just imports them and passes them to LangGraph.
"""

from __future__ import annotations

from typing import Iterator

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from config import cfg
from src.helpers.prompts import orchestrator_prompt
from src.helpers.langsmith_tracker import trace_run, ResearchRunMetadata
from src.agents.web_agent import call_web_agent
from src.agents.memory_agent import call_memory_agent
from src.agents.research_agent import call_research_agent
from src.agents.verifier_agent import call_verifier_agent
from src.agents.architecture_agent import call_architecture_agent
from memory_manager import bootstrap_memory_dir, load_memory_index


ORCHESTRATOR_TOOLS = [
    call_web_agent,
    call_memory_agent,
    call_research_agent,
    call_verifier_agent,
    call_architecture_agent,
]


def build_orchestrator():
    bootstrap_memory_dir()
    memory_index = load_memory_index()

    llm = ChatOllama(
        model=cfg.OLLAMA_MODEL,
        base_url=cfg.OLLAMA_BASE_URL,
        temperature=0,
    )

    return create_react_agent(
        model=llm,
        tools=ORCHESTRATOR_TOOLS,
        prompt=SystemMessage(content=orchestrator_prompt(memory_index)),
    )


class Orchestrator:

    def __init__(self):
        self.graph = build_orchestrator()

    def run(self, query: str, verbose: bool = True) -> str:
        meta = ResearchRunMetadata(topic=query, tags=["orchestrator", "react"])
        with trace_run(f"orchestrator: {query}", metadata=meta):
            return self._run(query, verbose)

    def _run(self, query: str, verbose: bool) -> str:
        print(f"\n{'=' * 66}")
        print(f"  ORCHESTRATOR — {query}")
        print(f"{'=' * 66}\n")

        inputs = {"messages": [HumanMessage(content=query)]}
        final_answer = ""

        for step_idx, state in enumerate(
            self.graph.stream(inputs, stream_mode="values")
        ):
            last = state["messages"][-1]
            kind = last.__class__.__name__

            if verbose:
                if kind == "AIMessage" and last.tool_calls:
                    print(f"\n[Orchestrator · step {step_idx}]  Reasoning -> Action")
                    for tc in last.tool_calls:
                        args_str = {k: str(v)[:80] for k, v in tc["args"].items()}
                        print(f"  agent : {tc['name']}")
                        print(f"  args  : {args_str}")
                elif kind == "ToolMessage":
                    preview = last.content[:200].replace("\n", " ")
                    print(f"\n[Orchestrator · step {step_idx}]  <- {last.name}")
                    print(f"  {preview}...")
                elif kind == "AIMessage" and not last.tool_calls:
                    print(f"\n[Orchestrator · step {step_idx}]  Final Answer ready")

            if kind == "AIMessage" and not last.tool_calls:
                final_answer = last.content

        return final_answer

    def stream(self, query: str) -> Iterator[dict]:
        inputs = {"messages": [HumanMessage(content=query)]}
        for step_idx, state in enumerate(
            self.graph.stream(inputs, stream_mode="values")
        ):
            last = state["messages"][-1]
            kind = last.__class__.__name__
            if kind == "AIMessage" and last.tool_calls:
                for tc in last.tool_calls:
                    yield {"step": step_idx, "type": "action",
                           "agent": tc["name"], "args": tc["args"]}
            elif kind == "ToolMessage":
                yield {"step": step_idx, "type": "observation",
                       "agent": last.name, "content": last.content}
            elif kind == "AIMessage" and not last.tool_calls:
                yield {"step": step_idx, "type": "final", "content": last.content}