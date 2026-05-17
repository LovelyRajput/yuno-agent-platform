"""Tests for the built-in tools."""
from __future__ import annotations

from app.agents.tools import calculator, current_time, echo, available_tool_names, get_tools


def test_calculator_basic():
    assert calculator.invoke({"expression": "2 + 3 * 4"}) == "2 + 3 * 4 = 14"


def test_calculator_math_functions():
    result = calculator.invoke({"expression": "sqrt(16) + 1"})
    assert "5" in result


def test_calculator_rejects_unsafe():
    out = calculator.invoke({"expression": "__import__('os').system('echo hi')"})
    assert "error" in out.lower()


def test_current_time_returns_iso_string():
    out = current_time.invoke({})
    assert "T" in out and out.endswith("Z")


def test_echo_returns_input():
    assert echo.invoke({"message": "hi there"}) == "hi there"


def test_get_tools_resolves_names():
    tools = get_tools(["calculator", "echo", "unknown_tool"])
    assert len(tools) == 2  # unknown silently dropped


def test_available_tool_names():
    names = available_tool_names()
    assert "web_search" in names and "calculator" in names
