"""Tests for agent CRUD."""
from __future__ import annotations


def test_create_and_list_agent(client):
    payload = {
        "name": "TestBot",
        "role": "tester",
        "system_prompt": "You test things.",
        "tools": ["calculator"],
    }
    r = client.post("/api/agents", json=payload)
    assert r.status_code == 201, r.text
    agent = r.json()
    assert agent["name"] == "TestBot"
    assert agent["tools"] == ["calculator"]
    assert agent["id"] > 0

    r2 = client.get("/api/agents")
    assert r2.status_code == 200
    agents = r2.json()
    assert any(a["id"] == agent["id"] for a in agents)


def test_update_and_delete_agent(client):
    create = client.post("/api/agents", json={"name": "Tmp"}).json()
    aid = create["id"]
    r = client.patch(f"/api/agents/{aid}", json={"system_prompt": "Updated"})
    assert r.status_code == 200
    assert r.json()["system_prompt"] == "Updated"

    r = client.delete(f"/api/agents/{aid}")
    assert r.status_code == 204
    r2 = client.get(f"/api/agents/{aid}")
    assert r2.status_code == 404


def test_list_tools(client):
    r = client.get("/api/agents/tools")
    assert r.status_code == 200
    names = r.json()
    # Required built-in tools
    for t in ("web_search", "calculator", "current_time", "echo"):
        assert t in names
