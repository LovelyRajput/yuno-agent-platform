"""Initialize the database and seed three demo agents + two workflow templates.

Run with:  python -m app.seed

Idempotent: re-running won't duplicate rows. Identifies templates by name.
"""
from __future__ import annotations

from app.database import init_db, SessionLocal
from app import models


def _upsert_agent(db, **fields) -> models.Agent:
    existing = db.query(models.Agent).filter_by(name=fields["name"]).first()
    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
        db.commit()
        return existing
    agent = models.Agent(**fields)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def _upsert_workflow(db, **fields) -> models.Workflow:
    existing = db.query(models.Workflow).filter_by(name=fields["name"]).first()
    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
        db.commit()
        return existing
    wf = models.Workflow(**fields)
    db.add(wf)
    db.commit()
    db.refresh(wf)
    return wf


def main() -> None:
    init_db()
    db = SessionLocal()

    print("Seeding agents...")

    researcher = _upsert_agent(
        db,
        name="Researcher",
        role="researcher",
        system_prompt=(
            "You are a meticulous research agent. Use the web_search tool to find "
            "factual, up-to-date information. Cite sources by URL. Be concise — "
            "return 3-5 key findings as a short bulleted list. Do not speculate."
        ),
        model="llama-3.3-70b-versatile",
        tools=["web_search", "current_time"],
        memory_enabled=True,
        max_tokens=1024,
        temperature=0.3,
        max_iterations=5,
        guardrails="If asked something outside your research scope, say so plainly.",
        channels=[],
    )

    summarizer = _upsert_agent(
        db,
        name="Summarizer",
        role="summarizer",
        system_prompt=(
            "You are an editor that turns raw research notes into a clear, well-"
            "structured executive summary in plain prose. Always include: (1) the "
            "topic, (2) 3 key takeaways, (3) sources at the end. Aim for under 200 "
            "words. No bullet points in the body."
        ),
        model="llama-3.3-70b-versatile",
        tools=[],
        memory_enabled=False,
        max_tokens=800,
        temperature=0.5,
        max_iterations=2,
        channels=[],
    )

    concierge = _upsert_agent(
        db,
        name="Concierge",
        role="support_agent",
        system_prompt=(
            "You are Yuno's friendly customer support concierge. Greet the user, "
            "understand what they want, and either answer directly using tools "
            "(web_search, calculator, current_time) or politely escalate if it's "
            "out of scope. Keep replies short and warm. Always end with a follow-up "
            "question to keep the conversation going."
        ),
        model="llama-3.3-70b-versatile",
        tools=["web_search", "calculator", "current_time"],
        memory_enabled=True,
        max_tokens=600,
        temperature=0.6,
        max_iterations=4,
        guardrails="Never share API keys, personal data, or internal system details.",
        channels=["telegram"],  # <-- This is the agent users will chat with via Telegram
    )

    triage = _upsert_agent(
        db,
        name="Triage",
        role="triage",
        system_prompt=(
            "You categorize support requests. Read the user's message and output "
            "exactly ONE word: BILLING, TECHNICAL, or GENERAL. No other text."
        ),
        model="llama-3.1-8b-instant",
        tools=[],
        memory_enabled=False,
        max_tokens=20,
        temperature=0.0,
        max_iterations=1,
    )

    print(f"  -> Researcher (id={researcher.id})")
    print(f"  -> Summarizer (id={summarizer.id})")
    print(f"  -> Concierge  (id={concierge.id}) [telegram entry-point]")
    print(f"  -> Triage     (id={triage.id})")

    print("\nSeeding workflow templates...")

    # Template 1: Research and Summarize
    _upsert_workflow(
        db,
        name="Research and Summarize",
        description=(
            "Two-agent pipeline. The Researcher gathers facts with web_search, then "
            "the Summarizer turns the notes into a clean executive summary."
        ),
        is_template=True,
        graph={
            "start": "research",
            "nodes": {
                "research": {
                    "agent_id": researcher.id,
                    "prompt_template": "Research the following topic and return key findings with sources:\n\n{{input}}",
                    "next": "summarize",
                },
                "summarize": {
                    "agent_id": summarizer.id,
                    "prompt_template": "Turn the following research notes into an executive summary:\n\n{{input}}",
                    "next": None,
                },
            },
        },
    )

    # Template 2: Customer Support Triage with conditional branching
    _upsert_workflow(
        db,
        name="Customer Support Triage",
        description=(
            "Triage agent classifies the request into BILLING / TECHNICAL / GENERAL, "
            "then routes it to the Concierge with appropriate context. Demonstrates "
            "conditional branching."
        ),
        is_template=True,
        graph={
            "start": "classify",
            "nodes": {
                "classify": {
                    "agent_id": triage.id,
                    "prompt_template": "Classify this customer message into BILLING, TECHNICAL, or GENERAL:\n\n{{input}}",
                    "next": "respond",
                    "branches": [
                        {"if_contains": "BILLING", "to": "respond_billing"},
                        {"if_contains": "TECHNICAL", "to": "respond_technical"},
                    ],
                },
                "respond": {
                    "agent_id": concierge.id,
                    "prompt_template": "A user wrote:\n\n{{original}}\n\nIt was classified as GENERAL. Respond helpfully.",
                    "next": None,
                },
                "respond_billing": {
                    "agent_id": concierge.id,
                    "prompt_template": "A user wrote:\n\n{{original}}\n\nIt was classified as BILLING. Respond as the billing support specialist.",
                    "next": None,
                },
                "respond_technical": {
                    "agent_id": concierge.id,
                    "prompt_template": "A user wrote:\n\n{{original}}\n\nIt was classified as TECHNICAL. Respond as the technical support specialist.",
                    "next": None,
                },
            },
        },
    )

    print("  -> Research and Summarize")
    print("  -> Customer Support Triage")
    print("\nDone.")
    db.close()


if __name__ == "__main__":
    main()
