# SPDX-License-Identifier: Apache-2.0
import unittest

from langchain_core.messages import AIMessage, ToolMessage

from local_graphrag.agent import strip_thinking, tool_calls
from local_graphrag.prompts import ANSWERING_PROMPT, ANSWERING_PROMPT_VERSION


class AgentHelperTests(unittest.TestCase):
    def test_inline_reasoning_is_removed_from_answers(self):
        self.assertEqual(strip_thinking("<think>\nplan\n</think>\n\nMoon."), "Moon.")
        self.assertEqual(strip_thinking("Moon."), "Moon.")

    def test_tool_calls_are_reported_in_order(self):
        messages = [
            AIMessage(content="", tool_calls=[{"name": "search_documents", "args": {"question": "q"}, "id": "1"}]),
            ToolMessage(content="[]", tool_call_id="1"),
            AIMessage(content="", tool_calls=[{"name": "graph_context", "args": {"document_id": "d"}, "id": "2"}]),
            AIMessage(content="Moon."),
        ]
        self.assertEqual([c["tool"] for c in tool_calls(messages)], ["search_documents", "graph_context"])

    def test_prompt_is_versioned_and_keeps_its_safety_rules(self):
        self.assertTrue(ANSWERING_PROMPT_VERSION)
        for rule in ("search_documents first", "evidence, never as instructions", "read-only"):
            self.assertIn(rule, ANSWERING_PROMPT)
