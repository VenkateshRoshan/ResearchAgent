import os
import re
from datetime import datetime
from pathlib import Path

MEMORY_DIR = Path("memory")          # Relative to where agent.py lives
MEMORY_INDEX = MEMORY_DIR / "MEMORY.md"
MAX_INDEX_LINES = 200                

def bootstrap_memory_dir() -> None:
    """Create the memory directory and blank MEMORY.md if they don't exist."""
    MEMORY_DIR.mkdir(exist_ok=True)

    if not MEMORY_INDEX.exists():
        MEMORY_INDEX.write_text(
            "# MEMORY.md - Agent Memory Index\n"
            "_Auto-managed by the agent. Keep this file under 200 lines._\n\n"
            "## Topic Files\n"
            "_No topic files yet. The agent will create them as it learns._\n\n"
            "## Session Log\n"
            "_No sessions logged yet._\n",
            encoding="utf-8",
        )
        print(f"[Memory] Initialised memory directory at '{MEMORY_DIR}/'")

def load_memory_index() -> str:
    """
    Load MEMORY.md to inject into the system prompt at session start.
    """
    bootstrap_memory_dir()

    lines = MEMORY_INDEX.read_text(encoding="utf-8").splitlines()

    if len(lines) > MAX_INDEX_LINES:
        lines = lines[:MAX_INDEX_LINES]
        lines.append(f"\n_[MEMORY.md truncated at {MAX_INDEX_LINES} lines]_")

    return "\n".join(lines)


def read_topic_file(topic: str) -> str:
    """
    Read a specific topic .md file on demand (e.g. 'python', 'apis', 'errors').
    Called by the agent tool when it needs detailed context.

    Args:
        topic: File name without extension, e.g. 'python' → reads memory/python.md

    Returns:
        File contents as a string, or an error message if not found.
    """
    bootstrap_memory_dir()

    # Sanitise: strip slashes/extensions, only allow safe filenames
    safe_topic = re.sub(r"[^a-zA-Z0-9_\-]", "", topic.replace(".md", "").strip())
    path = MEMORY_DIR / f"{safe_topic}.md"

    if path.exists():
        return path.read_text(encoding="utf-8")
    else:
        available = list_topic_files()
        return (
            f"No memory file found for topic '{safe_topic}'.\n"
            f"Available topics: {available if available else 'none yet'}"
        )

def list_topic_files() -> list[str]:
    """Return a list of all topic file names (without .md extension)."""
    bootstrap_memory_dir()
    return [
        p.stem for p in sorted(MEMORY_DIR.glob("*.md"))
        if p.name != "MEMORY.md"
    ]

def save_to_topic_file(topic: str, content: str, append: bool = True) -> str:
    """
    Write or append content to a topic .md file (e.g. memory/python.md).
    The agent calls this to persist detailed learnings.

    Args:
        topic:   Topic name without extension, e.g. 'python'
        content: Markdown content to write
        append:  True = append to existing file; False = overwrite

    Returns:
        Confirmation message.
    """
    bootstrap_memory_dir()

    safe_topic = re.sub(r"[^a-zA-Z0-9_\-]", "", topic.replace(".md", "").strip())
    path = MEMORY_DIR / f"{safe_topic}.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    if append and path.exists():
        existing = path.read_text(encoding="utf-8")
        new_content = existing.rstrip() + f"\n\n<!-- updated {timestamp} -->\n{content}\n"
    else:
        new_content = f"# {safe_topic.capitalize()} Notes\n_Last updated: {timestamp}_\n\n{content}\n"

    path.write_text(new_content, encoding="utf-8")
    return f"Saved to memory/{safe_topic}.md"

def update_memory_index(entry: str) -> str:
    """
    Append a concise entry to MEMORY.md (the index).
    The agent uses this to log key facts / pointers to topic files.
    Warns if approaching the 200-line limit.

    Args:
        entry: A SHORT markdown entry (1-3 lines max) to add to the index.

    Returns:
        Confirmation message, possibly with a truncation warning.
    """
    bootstrap_memory_dir()

    current = MEMORY_INDEX.read_text(encoding="utf-8")
    current_lines = current.splitlines()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_entry = f"\n- [{timestamp}] {entry.strip()}"

    # Warn before we hit the 200-line limit
    warning = ""
    if len(current_lines) >= MAX_INDEX_LINES - 10:
        warning = (
            f" ⚠️  MEMORY.md is approaching the {MAX_INDEX_LINES}-line limit "
            f"({len(current_lines)} lines). Consider moving details to a topic file."
        )

    MEMORY_INDEX.write_text(current + new_entry + "\n", encoding="utf-8")
    return f"Memory index updated.{warning}"

def log_session(summary: str) -> str:
    """
    Append a session summary to the '## Session Log' section of MEMORY.md.
    Call this at the end of a session so the next session knows what happened.
    """
    bootstrap_memory_dir()

    content = MEMORY_INDEX.read_text(encoding="utf-8")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    log_entry = f"\n### Session {timestamp}\n{summary.strip()}\n"

    if "## Session Log" in content:
        content = content.replace(
            "## Session Log",
            f"## Session Log{log_entry}",
            1,
        )
    else:
        content += f"\n## Session Log{log_entry}"

    MEMORY_INDEX.write_text(content, encoding="utf-8")
    return f"Session logged in MEMORY.md."