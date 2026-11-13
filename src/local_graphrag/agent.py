# SPDX-License-Identifier: Apache-2.0
import asyncio
import re

from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama

from .prompts import ANSWERING_PROMPT, ANSWERING_PROMPT_VERSION

# Some local models (for example qwen3) can emit their reasoning inline.
THINKING = re.compile(r"<think>.*?</think>\s*", re.DOTALL)
# Maximum LangGraph steps (model turns plus tool calls) before the agent stops.
# Enough for search → several graph_context calls → answer; stops runaway tool loops.
RECURSION_LIMIT = 16


def strip_thinking(text):
    return THINKING.sub("", text).strip()


def tool_calls(messages):
    """Return the ordered tool calls the model made, for inspection and evaluation."""
    return [{"tool": call["name"], "args": call["args"]}
            for message in messages for call in (getattr(message, "tool_calls", None) or [])]


async def ask(settings, question, trace=False):
    client = MultiServerMCPClient({"graph": {"url": settings.mcp_url, "transport": "http"}})
    tools = await client.get_tools()
    agent = create_agent(
        ChatOllama(model=settings.chat_model, base_url=settings.ollama, temperature=0),
        tools=tools,
        system_prompt=ANSWERING_PROMPT,
    )
    try:
        result = await asyncio.wait_for(
            agent.ainvoke({"messages": [{"role": "user", "content": question}]},
                          config={"recursion_limit": RECURSION_LIMIT}),
            timeout=settings.answer_timeout)
    except asyncio.TimeoutError:
        raise TimeoutError(f"No answer within {settings.answer_timeout} s; "
                           "check Ollama or raise ANSWER_TIMEOUT_SECONDS") from None
    answer = strip_thinking(result["messages"][-1].content)
    if not trace:
        return answer
    return {"model": settings.chat_model, "prompt_version": ANSWERING_PROMPT_VERSION,
            "tool_calls": tool_calls(result["messages"]), "answer": answer}
