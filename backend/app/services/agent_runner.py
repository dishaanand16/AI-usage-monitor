"""
Support agent runner.

A deliberately small agent (no LangGraph/LangChain framework overhead —
see README for why) that answers a support query using two tools:
FAQ Database and Orders Database. It is DECLARED (in ai_assets.declared_
data_sources) to only use FAQ Database, but for order-related queries it
will also call Orders Database — this is the seeded "unexpected access"
case described in the brief's End-to-End Example.

Every tool call is logged as it happens (not inferred after the fact),
which is what lets us compute declared vs. observed access truthfully.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Callable


# ---------------------------------------------------------------------------
# Mock data sources (stand-ins for real DB-backed tools; swapping these for
# real DB queries would not change the logging/observability approach).
# ---------------------------------------------------------------------------

def faq_database_lookup(query: str) -> str:
    return "Our support hours are 9am-6pm IST, Monday to Saturday."


def orders_database_lookup(order_ref: str) -> str:
    return f"Order {order_ref} was shipped 2 days ago and is out for delivery."


def mock_llm_call(prompt: str) -> dict:
    """Stand-in for a real provider call. Swap for a real Anthropic call to
    validate against production behavior — logging shape is identical."""
    time.sleep(0.05)
    return {
        "model": "claude-mock-1",
        "text": f"Based on the context, here's the answer to: {prompt[:40]}...",
        "usage": {"input_tokens": len(prompt.split()), "output_tokens": 18},
    }


# ---------------------------------------------------------------------------
# Instrumentation: every tool call and LLM call appends a structured event.
# This is the "code instrumentation" approach from Day 1's research —
# events are captured explicitly by the agent itself, not inferred from
# network traffic (which a gateway alone could not achieve).
# ---------------------------------------------------------------------------

@dataclass
class RunEvents:
    tool_accesses: list = field(default_factory=list)   # source names touched
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


def run_support_agent(user_query: str) -> RunEvents:
    events = RunEvents()

    # Every agent run starts by consulting FAQ — this matches what's
    # DECLARED for this asset.
    events.tool_accesses.append("FAQ Database")
    faq_context = faq_database_lookup(user_query)

    # Simple heuristic: if the query mentions an order, the agent also
    # reaches into Orders Database — a source it was NOT declared to use.
    # This is intentional: it's the seeded governance-insight scenario.
    if "order" in user_query.lower():
        events.tool_accesses.append("Orders Database")
        orders_context = orders_database_lookup("ORD-4471")
        full_context = f"{faq_context} {orders_context}"
    else:
        full_context = faq_context

    llm_response = mock_llm_call(f"{user_query}\nContext: {full_context}")
    events.model = llm_response["model"]
    events.input_tokens = llm_response["usage"]["input_tokens"]
    events.output_tokens = llm_response["usage"]["output_tokens"]

    return events


if __name__ == "__main__":
    # Manual sanity check — matches the brief's End-to-End Example.
    result = run_support_agent("Where is my order and what are your support hours?")
    print("Tool accesses:", result.tool_accesses)
    print("Model:", result.model)
    print("Tokens:", result.input_tokens, result.output_tokens)