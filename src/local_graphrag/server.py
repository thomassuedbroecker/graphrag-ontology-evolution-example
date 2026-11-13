# SPDX-License-Identifier: Apache-2.0
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse
from urllib.parse import urlparse

from .config import Settings
from .store import Store


def create_server(store):
    server = FastMCP("Local Galaxium GraphRAG")

    @server.custom_route("/health", methods=["GET"])
    async def health(request: Request):
        return JSONResponse({"status": "ok"})

    @server.tool()
    def search_documents(question: str, limit: int = 3) -> list[dict]:
        """Find local source passages by semantic similarity. Returns source IDs for citation."""
        return store.search(question, limit)

    @server.tool()
    def graph_context(document_id: str) -> list[dict]:
        """Find facts connected to a retrieved document's entities, including other documents."""
        return store.context(document_id)

    return server


def serve():
    settings = Settings.load()
    endpoint = urlparse(settings.mcp_url)
    store = Store(settings)
    try:
        create_server(store).run(
            transport="http", host=endpoint.hostname, port=endpoint.port or 80,
            path=endpoint.path or "/mcp",
        )
    finally:
        store.close()
