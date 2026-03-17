"""
main.py — Entry Point
══════════════════════
Starts the CLI and passes every query to the Router.
Contains zero business logic — that all lives in:
  src/router.py        ← routing + tracking
  src/orchestrator.py  ← ReAct reasoning loop
  src/agents/          ← specialist agents

Usage:
    python main.py                     # interactive CLI
    python main.py "your topic here"   # one-shot
"""

from __future__ import annotations

import sys

from src.router import Router
from src.helpers.langsmith_tracker import setup_tracing
from memory_manager import bootstrap_memory_dir, load_memory_index, list_topic_files, read_topic_file

def main() -> None:
    setup_tracing()
    bootstrap_memory_dir()

    router = Router(verbose=True)

    # One-shot mode
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        result = router.route(query)
        print(result.display())
        return

    # Interactive mode
    while True:
        try:
            user_input = input("Query: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        # CLI utility commands
        if user_input.lower() == "/memory":
            print("\n" + load_memory_index() + "\n")
            continue

        if user_input.lower() == "/topics":
            t = list_topic_files()
            print(f"\n{', '.join(t) if t else 'none yet'}\n")
            continue

        if user_input.lower().startswith("/read "):
            print("\n" + read_topic_file(user_input[6:].strip()) + "\n")
            continue

        if user_input.lower() == "/diagrams":
            from src.agents.architecture_agent import ArchitectureAgent
            diagrams = ArchitectureAgent().list_diagrams()
            print(f"\nDiagrams: {', '.join(diagrams) if diagrams else 'none yet'}\n")
            continue

        # Route the query
        result = router.route(user_input)
        print(result.display())


if __name__ == "__main__":
    main()


# I would like to get more information on my project BCI + EEG + AI Agent for disabled people to give mobility back using exo-skeletons, where AI models will detect the motor imagery classification