"""Real tools agents can invoke. These execute actual work — not stubs."""
from __future__ import annotations

import math
from datetime import datetime
from typing import List

from langchain_core.tools import tool


@tool
def web_search(query: str) -> str:
    """Search the web with DuckDuckGo and return the top 5 results as text.

    Args:
        query: The search query.
    """
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        if not results:
            return f"No results found for '{query}'."
        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            lines.append(f"{i}. {title}\n   {body}\n   {href}")
        return "\n\n".join(lines)
    except Exception as e:  # pragma: no cover - network errors
        return f"web_search failed: {e}"


@tool
def calculator(expression: str) -> str:
    """Safely evaluate a mathematical expression. Supports +, -, *, /, **, parentheses,
    and common math functions (sqrt, sin, cos, tan, log, pi, e).

    Args:
        expression: A math expression like '2 + 2 * sqrt(16)'.
    """
    allowed = {
        "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "log": math.log, "log10": math.log10, "exp": math.exp,
        "pi": math.pi, "e": math.e, "abs": abs, "round": round,
        "min": min, "max": max, "pow": pow,
    }
    try:
        result = eval(expression, {"__builtins__": {}}, allowed)
        return f"{expression} = {result}"
    except Exception as e:
        return f"calculator error: {e}"


@tool
def current_time() -> str:
    """Return the current UTC date and time in ISO format."""
    return datetime.utcnow().isoformat() + "Z"


@tool
def echo(message: str) -> str:
    """Return the input verbatim. Useful for testing and simple workflows.

    Args:
        message: The message to echo back.
    """
    return message


# Registry: name -> tool object. Agents reference tools by name.
TOOL_REGISTRY = {
    "web_search": web_search,
    "calculator": calculator,
    "current_time": current_time,
    "echo": echo,
}


def get_tools(names: List[str]):
    """Resolve a list of tool names to LangChain tool objects."""
    return [TOOL_REGISTRY[n] for n in names if n in TOOL_REGISTRY]


def available_tool_names() -> List[str]:
    return list(TOOL_REGISTRY.keys())
