"""
src/agents/memory_agent.py
───────────────────────────
Memory Agent - owns Write Tool and Read Tool.
Exposes call_memory_agent as the orchestrator-facing @tool.
"""

from __future__ import annotations

from langchain_core.tools import tool

from memory_manager import (
    read_topic_file, save_to_topic_file, update_memory_index,
    list_topic_files, log_session,
)

@tool
def write_tool(topic: str, content: str) -> str:
    """Write research notes to memory/<topic>.md."""
    result = save_to_topic_file(topic, content, append=True)
    update_memory_index(f"Research saved -> memory/{topic}.md")
    return result

@tool
def read_tool(topic: str) -> str:
    """Read stored notes for a topic from memory/<topic>.md."""
    return read_topic_file(topic)

class MemoryAgent:
    TOOLS = [write_tool, read_tool]

    def execute(self, action: str, topic: str = "", content: str = "", entry: str = "") -> str:
        action = action.lower().strip()
        if action == "list":
            topics = list_topic_files()
            return ("Stored topics: " + ", ".join(topics)) if topics else "No topics stored yet."
        elif action == "read":
            return read_tool.invoke({"topic": topic})
        elif action == "write":
            return write_tool.invoke({"topic": topic, "content": content})
        elif action == "index":
            return update_memory_index(entry)
        elif action == "log":
            return log_session(content)
        else:
            return f"Unknown action '{action}'. Valid: list, read, write, index, log"

_instance = None

def _get() -> MemoryAgent:
    global _instance
    if _instance is None:
        _instance = MemoryAgent()
    return _instance

@tool
def call_memory_agent(action: str, topic: str = "", content: str = "", entry: str = "") -> str:
    """
    Call the Memory Agent to read or write persistent .md memory files.

    Actions:
      list  - list all stored topics
      read  - read a topic file (requires: topic)
      write - save notes (requires: topic, content)
      index - add short line to MEMORY.md (requires: entry)
      log   - log session summary (requires: content)

    Args:
        action:  One of: list, read, write, index, log
        topic:   Topic slug for read/write
        content: Content to write or session summary
        entry:   Short one-line index entry
    """
    print(f"\n  [Memory Agent]  action={action} topic={topic or '-'}")
    return _get().execute(action=action, topic=topic, content=content, entry=entry)