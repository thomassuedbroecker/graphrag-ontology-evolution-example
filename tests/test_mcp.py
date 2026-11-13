# SPDX-License-Identifier: Apache-2.0
import unittest

import httpx

from fastmcp import Client

from local_graphrag.server import create_server


class FixtureStore:
    def search(self, question, limit):
        return [{"document_id": "company-overview", "source": "synthetic:test"}]

    def context(self, document_id):
        return [{"subject": "Lunar Discovery", "relation": "VISITS", "object": "Moon"}]


class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_http_health_endpoint(self):
        app = create_server(FixtureStore()).http_app()
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                result = await client.get("/health")
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json(), {"status": "ok"})

    async def test_read_only_tool_discovery_and_calls(self):
        async with Client(create_server(FixtureStore())) as client:
            self.assertEqual({t.name for t in await client.list_tools()},
                             {"search_documents", "graph_context"})
            result = await client.call_tool("search_documents", {"question": "Where?"})
            self.assertFalse(result.is_error)
            self.assertIn("company-overview", str(result.content))
            result = await client.call_tool("graph_context", {"document_id": "company-overview"})
            self.assertFalse(result.is_error)
            self.assertIn("Moon", str(result.content))
