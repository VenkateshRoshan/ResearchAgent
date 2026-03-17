"""
config.py
─────────
Single source of truth for all environment variables and settings.
Loads from a .env file automatically via python-dotenv.

Usage:
    from config import cfg
    print(cfg.OLLAMA_MODEL)
"""

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv(dotenv_path=Path(__file__).parent / ".env")


@dataclass(frozen=True)
class Config:
    OLLAMA_MODEL: str    = "qwen2.5:7b"
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    TEMPERATURE: float   = float(os.getenv("TEMPERATURE", "0"))
    OLLAMA_NUM_CTX: int = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
    OLLAMA_NUM_PREDICT: int = int(os.getenv("OLLAMA_NUM_PREDICT", "4096"))

    LANGCHAIN_TRACING_V2: str  = os.getenv("LANGCHAIN_TRACING_V2", "false")
    LANGCHAIN_API_KEY: str     = os.getenv("LANGCHAIN_API_KEY", "")
    LANGCHAIN_PROJECT: str     = os.getenv("LANGCHAIN_PROJECT", "personal-research-agent")
    LANGCHAIN_ENDPOINT: str    = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")

    MEMORY_DIR: str = os.getenv("MEMORY_DIR", "memory")

    # Max web searches the research agent may fire per topic
    MAX_SEARCH_RESULTS: int = int(os.getenv("MAX_SEARCH_RESULTS", "5"))

    def is_langsmith_enabled(self) -> bool:
        return self.LANGCHAIN_TRACING_V2.lower() == "true" and bool(self.LANGCHAIN_API_KEY)

    def __post_init__(self):
        # Push LangSmith vars into the process environment so LangChain picks them up
        if self.is_langsmith_enabled():
            os.environ["LANGCHAIN_TRACING_V2"]  = self.LANGCHAIN_TRACING_V2
            os.environ["LANGCHAIN_API_KEY"]      = self.LANGCHAIN_API_KEY
            os.environ["LANGCHAIN_PROJECT"]      = self.LANGCHAIN_PROJECT
            os.environ["LANGCHAIN_ENDPOINT"]     = self.LANGCHAIN_ENDPOINT


# Singleton — import this everywhere
cfg = Config()

_llm_instance: ChatOllama | None = None


def get_llm() -> ChatOllama:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = ChatOllama(
            model=cfg.OLLAMA_MODEL,
            base_url=cfg.OLLAMA_BASE_URL,
            temperature=cfg.TEMPERATURE,
            num_ctx=cfg.OLLAMA_NUM_CTX,
            num_predict=cfg.OLLAMA_NUM_PREDICT,
        )
    return _llm_instance
