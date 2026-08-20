"""
Support agent runner — LangGraph + real LLM version.

Unlike the earlier keyword-heuristic version, this agent uses a real LLM
(via Groq) to genuinely DECIDE which tools to call based on the user's
query. This is closer to how a production agent behaves: the model reads
the query, reasons about what it needs, and invokes tools accordingly —
which means "unexpected access" here is a real emergent behavior of the
LLM's reasoning, not something we hardcoded with an if-statement.

We still log every tool invocation ourselves via a callback, because the
brief specifically requires the MONITORING SYSTEM (not the LLM) to be the
source of truth for what was actually accessed — an agent's own claims
about what it did should not be trusted as the audit record.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_groq import ChatGroq
from langchain.agents import create_agent

# .env lives at the project root (flyyy-ai/), three levels up from this
# file (backend/app/services/agent_runner.py) -- resolve it explicitly so
# this works regardless of which directory the script is run from.
_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(dotenv_path=_ENV_PATH)
GROQ_MODEL = "openai/gpt-oss-20b"


# ---------------------------------------------------------------------------
# Tools -- real LangChain @tool-decorated functions the LLM can choose to call.
# ---------------------------------------------------------------------------

@tool
def faq_database_lookup(query: str) -> str:
    """Look up general support FAQ information such as support hours,
    policies, or shipping information."""
    return "Our support hours are 9am-6pm IST, Monday to Saturday."


@tool
def orders_database_lookup(order_reference: str) -> str:
    """Look up the status of a specific customer order, given an order
    reference or general request about 'my order'."""
    return f"Order {order_reference or 'ORD-4471'} was shipped 2 days ago and is out for delivery."


TOOLS = [faq_database_lookup, orders_database_lookup]


# ---------------------------------------------------------------------------
# Monitoring callback -- this is our observability layer. It listens for
# every tool call the agent makes and records it independently of what
# the agent later claims in its final answer.
# ---------------------------------------------------------------------------

class ToolAccessLogger(BaseCallbackHandler):
    def __init__(self):
        self.accessed_sources = []

    def on_tool_start(self, serialized, input_str, **kwargs):
        tool_name = serialized.get("name", "unknown_tool")
        source_map = {
            "faq_database_lookup": "FAQ Database",
            "orders_database_lookup": "Orders Database",
        }
        self.accessed_sources.append(source_map.get(tool_name, tool_name))


@dataclass
class RunEvents:
    tool_accesses: list = field(default_factory=list)
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    final_answer: str = ""


def run_support_agent(user_query: str) -> RunEvents:
    llm = ChatGroq(
        model=GROQ_MODEL,
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0,
    )

    agent = create_agent(llm, TOOLS)

    logger = ToolAccessLogger()

    result = agent.invoke(
        {"messages": [("user", user_query)]},
        config={"callbacks": [logger]},
    )

    final_message = result["messages"][-1]
    final_answer = final_message.content if hasattr(final_message, "content") else str(final_message)

    # Token usage: pull from the last AI message's usage metadata if present.
    input_tokens = output_tokens = 0
    for msg in result["messages"]:
        usage = getattr(msg, "usage_metadata", None)
        if usage:
            input_tokens = usage.get("input_tokens", input_tokens)
            output_tokens = usage.get("output_tokens", output_tokens)

    return RunEvents(
        tool_accesses=logger.accessed_sources,
        model=GROQ_MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        final_answer=final_answer,
    )


if __name__ == "__main__":
    result = run_support_agent(
        "Where is my order ORD-4471 and what are your support hours?"
    )
    print("Tool accesses:", result.tool_accesses)
    print("Model:", result.model)
    print("Tokens:", result.input_tokens, result.output_tokens)
    print("Answer:", result.final_answer)