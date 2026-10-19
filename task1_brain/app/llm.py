"""Thin Claude wrapper: structured output via forced tool use, plus a cost/latency ledger."""
import os
import time
from typing import Any

from anthropic import AsyncAnthropic

# USD per 1M tokens (input, output). PLACEHOLDERS - verify at anthropic.com/pricing before you quote numbers.
PRICES = {
    "claude-haiku-5-5": (1.0, 5.0),
    "claude-sonnet-5-5": (3.0, 15.0),
    "claude-opus-5-5": (5.0, 25.0),
}
LEDGER: list[dict[str, Any]] = []
_client: AsyncAnthropic | None = None


def client() -> AsyncAnthropic:
    global _client
    if _client is None:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        _client = AsyncAnthropic(max_retries=4, timeout=90)
    return _client


def cost_usd(model: str, tin: int, tout: int) -> float:
    pin, pout = PRICES.get(model, (3.0, 15.0))
    return (tin * pin + tout * pout) / 1_000_000


async def call(model: str, system: str, content: Any, schema: dict | None = None,
               tool_name: str = "respond", max_tokens: int = 1500, label: str = "") -> Any:
    """Return parsed dict when `schema` is given (forced tool call), else plain text."""
    kw: dict[str, Any] = dict(model=model, max_tokens=max_tokens, system=system,
                              messages=[{"role": "user", "content": content}])
    if schema:
        kw["tools"] = [{"name": tool_name, "description": "Return the result.", "input_schema": schema}]
        kw["tool_choice"] = {"type": "tool", "name": tool_name}
    t0 = time.perf_counter()
    r = await client().messages.create(**kw)
    ms = int((time.perf_counter() - t0) * 1000)
    LEDGER.append({"label": label, "model": model, "ms": ms, "in": r.usage.input_tokens,
                   "out": r.usage.output_tokens,
                   "usd": cost_usd(model, r.usage.input_tokens, r.usage.output_tokens)})
    if schema:
        for b in r.content:
            if b.type == "tool_use":
                return b.input
        raise ValueError("model returned no tool call")
    return "".join(b.text for b in r.content if b.type == "text")


def ledger_total(since: int = 0) -> dict[str, float]:
    rows = LEDGER[since:]
    return {"calls": len(rows), "usd": round(sum(r["usd"] for r in rows), 6),
            "ms": sum(r["ms"] for r in rows)}
