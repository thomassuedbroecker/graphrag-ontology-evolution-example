# SPDX-License-Identifier: Apache-2.0
import os
from dataclasses import dataclass
from urllib.parse import urlparse

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    uri: str
    username: str
    password: str
    database: str
    ollama: str
    chat_model: str
    embed_model: str
    dimensions: int
    mcp_url: str
    answer_timeout: int = 300

    @classmethod
    def load(cls):
        load_dotenv()
        if not os.getenv("NEO4J_PASSWORD"):
            raise ValueError("NEO4J_PASSWORD is not set; run ./scripts/setup.sh to create .env from .env.example")
        settings = cls(
            os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
            os.getenv("NEO4J_USERNAME", "neo4j"),
            os.environ["NEO4J_PASSWORD"],
            os.getenv("NEO4J_DATABASE", "neo4j"),
            os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            os.getenv("OLLAMA_CHAT_MODEL", "qwen3:8b"),
            os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
            int(os.getenv("EMBEDDING_DIMENSIONS", "768")),
            os.getenv("MCP_URL", "http://127.0.0.1:8000/mcp"),
            int(os.getenv("ANSWER_TIMEOUT_SECONDS", "300")),
        )
        for url in (settings.uri, settings.ollama, settings.mcp_url):
            if urlparse(url).hostname not in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError(f"This example requires a loopback endpoint: {url}")
        for url in (settings.ollama, settings.mcp_url):
            endpoint = urlparse(url)
            if endpoint.scheme != "http" or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
                raise ValueError(f"Local HTTP endpoints require plain http without credentials/query/fragment: {url}")
        if urlparse(settings.ollama).path not in {"", "/"}:
            raise ValueError("OLLAMA_BASE_URL must be an origin without a path")
        if settings.dimensions <= 0:
            raise ValueError("EMBEDDING_DIMENSIONS must be positive")
        if settings.answer_timeout <= 0:
            raise ValueError("ANSWER_TIMEOUT_SECONDS must be positive")
        return settings
