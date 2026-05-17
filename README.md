# Yuno AI — Agent Orchestration Platform

> Submission for the Yuno AI Engineer Hiring Challenge — AI Agent Orchestration Platform.

A self-hostable platform for creating AI agents, configuring how they behave, and connecting them into collaborative workflows. Agents run on a real LangGraph-powered runtime, execute real tools (web search, calculator, time), and communicate with each other. One agent — the **Concierge** — is reachable through **Telegram** so a human can chat with it conversationally. Everything (agents, workflows, runs, messages) is managed through a web UI.

The platform uses **Groq** as the LLM provider (Llama 3.3 70B + Llama 3.1 8B Instant) so it runs on a free tier with no payment required. Swapping to another LangChain-supported provider (Anthropic, OpenAI, local Ollama) is a one-line change in `app/agents/runtime.py`.

---

## Demo

A short screen recording (`demo.mp4` / Loom link) is included showing:

1. Browsing seeded agents and templates in the web UI
2. Running the **Research and Summarize** workflow end-to-end (two agents collaborating)
3. Messaging the Telegram bot live and watching the conversation appear in the Live Monitor

---

## Architecture

```
                                     +----------------------+
                                     |      Web Browser     |
                                     |  (HTML + Tailwind +  |
                                     |     vanilla JS)      |
                                     +-----------+----------+
                                                 | REST + WebSocket
                                                 v
 +-----------------------------------------------------------------+
 |                       FastAPI application                       |
 |                                                                 |
 |  +-------------+   +--------------+   +-----------------------+ |
 |  |  Routers    |   |  WebSocket   |   |  Telegram bot         | |
 |  |  /api/...   |   |  /ws/monitor |   |  (long polling)       | |
 |  +------+------+   +------+-------+   +-----------+-----------+ |
 |         |                 |                       |             |
 |         v                 v                       v             |
 |  +-----------------------------------------------------------+  |
 |  |  Workflow orchestrator (app/agents/workflow.py)           |  |
 |  |    - walks the workflow graph                             |  |
 |  |    - branching / conditions / loops                       |  |
 |  |    - pipes output of agent N -> input of agent N+1        |  |
 |  +-------------------------+---------------------------------+  |
 |                            v                                    |
 |  +-----------------------------------------------------------+  |
 |  |  Agent runtime (app/agents/runtime.py)                    |  |
 |  |    LangGraph ReAct executor + ChatGroq (Llama 3.3 70B)    |  |
 |  |    - tool calling loop                                    |  |
 |  |    - token + cost tracking                                |  |
 |  |    - emits live events to the in-process EventBus         |  |
 |  +-------------------------+---------------------------------+  |
 |                            v                                    |
 |  +-----------------------------------------------------------+  |
 |  |  Persistence (SQLAlchemy + SQLite)                        |  |
 |  |  tables: agents, workflows, runs, messages, telegram_chats|  |
 |  +-----------------------------------------------------------+  |
 +-----------------------------------------------------------------+
                                      ^
                                      | HTTPS
                              +-------+--------+
                              |   Telegram     |
                              |  (user chat)   |
                              +----------------+
```

### Layers

| Layer            | Responsibility                                                     | Files |
|------------------|--------------------------------------------------------------------|-------|
| **UI**           | Server-rendered shells + vanilla JS that calls the JSON API        | `app/templates/`, `app/main.py` (page routes) |
| **API**          | REST CRUD for agents/workflows/runs + WebSocket for live monitor   | `app/routers/` |
| **Orchestrator** | Walks workflow graphs, handles branches/loops, async               | `app/agents/workflow.py` |
| **Runtime**      | LangGraph ReAct loop on top of Groq, tool calls, token tracking    | `app/agents/runtime.py`, `app/agents/tools.py` |
| **Channels**     | Adapters for external messaging — Telegram today, more later       | `app/channels/telegram_bot.py` |
| **Persistence**  | SQLAlchemy ORM + SQLite (file-based, zero setup)                   | `app/database.py`, `app/models.py` |
| **Events**       | In-process pub/sub feeding the WebSocket live monitor              | `app/events.py` |

---

## Tech stack and justifications

| Decision                  | Choice                              | Why |
|---------------------------|-------------------------------------|-----|
| Language (backend)        | **Python 3.12**                     | Best AI/LLM ecosystem. LangGraph, LangChain, Groq SDK and python-telegram-bot are all first-class here. Python 3.12 specifically because pydantic-core wheels are not yet available for 3.13/3.14. |
| Agent framework           | **LangGraph** (`create_react_agent`) | Built-in ReAct loop, async streaming, easy to swap LLMs, and well-suited to the "agents-as-graph-nodes" model the challenge describes. CrewAI is more opinionated; AutoGen is heavier; a custom runtime would be slower to ship. |
| LLM provider              | **Groq** (Llama 3.3 70B + Llama 3.1 8B Instant) | Generous free tier with no payment required — critical for an evaluator who needs to run the project locally without billing setup. Groq's hosted inference is also exceptionally fast (sub-second), which keeps the live demo snappy. Swappable to Anthropic / OpenAI / Ollama with a one-line change in `runtime.py`. |
| Web framework             | **FastAPI**                         | Native async (the orchestrator awaits LLM streams), automatic OpenAPI docs at `/docs`, easy WebSockets. |
| Persistence               | **SQLite** via SQLAlchemy           | Single-file database — satisfies the "fully local with a single setup command" requirement. Schema is portable to Postgres without code changes. |
| Frontend                  | **Tailwind (CDN) + vanilla JS + Jinja2** | Zero build step. Same single-command setup story. UI features required by the spec (CRUD forms, workflow builder, live monitor) don't need a SPA. |
| Messaging channel         | **Telegram** (`python-telegram-bot`) | Fastest of the three options to demo end-to-end: 2-minute bot creation via @BotFather, no business verification (unlike WhatsApp), no workspace setup (unlike Slack). |
| Live monitoring transport | **WebSocket + in-process EventBus** | Avoids a separate broker (Redis/RabbitMQ) while still giving real-time push. Trivial to swap for Redis pub/sub later. |
| Tests                     | **pytest + pytest-asyncio**         | Runtime is mocked in tests so they pass with no API keys (CI-friendly). |

---

## Setup (single command)

### Prerequisites

- **Python 3.12** (Python 3.13 and 3.14 are not yet supported by pydantic-core wheels at the time of writing)
- A **Groq API key** — free at <https://console.groq.com/keys> (sign in with Google or GitHub, no card required)
- A **Telegram bot token** — see "Telegram setup" below (takes 2 minutes)

### Setup

**Windows:**

```
setup.bat
```

**macOS / Linux:**

```
chmod +x setup.sh run.sh
./setup.sh
```

This will:

1. Create a Python virtual environment in `.venv/`
2. Install all dependencies from `requirements.txt`
3. Copy `.env.example` to `.env` (you must fill in your keys)
4. Initialize the SQLite database and seed 4 agents + 2 workflow templates

Open `.env` and fill in:

```
GROQ_API_KEY=gsk_...
TELEGRAM_BOT_TOKEN=12345:AAAA...
```

### Run

```
run.bat        (Windows)
./run.sh       (macOS / Linux)
```

Open <http://localhost:8000> in your browser.

---

## Telegram setup (2 minutes)

1. Open Telegram and search for `@BotFather`.
2. Send `/newbot`. Pick a name, then a username ending in `bot` (e.g. `yuno_demo_bot`).
3. BotFather replies with a token. Paste it into `.env` as `TELEGRAM_BOT_TOKEN`.
4. Restart the server. The seeded **Concierge** agent is already wired to the `telegram` channel.
5. In Telegram, search your bot's username, hit `/start`, and chat.

Every message you send becomes a Run in the platform. Watch it stream in `http://localhost:8000/monitor`.

---

## Demo walk-through

1. **Open** `http://localhost:8000`.
2. **Agents page**: see Researcher, Summarizer, Concierge (Telegram entry-point), Triage.
3. **Workflows page**: run **Research and Summarize** with input like *"What is Groq and why is it fast?"*. You'll see the Researcher use `web_search` then the Summarizer produce a clean summary.
4. **Live Monitor**: open `/monitor` in another tab. Now message your Telegram bot — watch `telegram_in`, `agent_start`, tool calls, `agent_done`, `telegram_out` stream in.
5. **Run history**: open `/runs` and click any run to see the full message log (user input, inter-agent messages, tool calls, tool results, replies).

---

## How configurable is an agent?

Per the impact metric *"Number of configurable dimensions per agent"*, an agent currently exposes:

1. Name
2. Role
3. System prompt
4. Model (Llama 3.3 70B / Llama 3.1 8B Instant on Groq)
5. Temperature
6. Max tokens
7. Max iterations (reasoning loop cap)
8. Tools (multi-select from registry: `web_search`, `calculator`, `current_time`, `echo` — easy to extend)
9. Channels (`telegram`)
10. Memory enabled flag
11. Guardrails (free-text, appended to system prompt)
12. Schedule (cron string, informational for the MVP)

---

## Extending the platform

### Add a new tool

Open `app/agents/tools.py`, define a function with `@tool`, and register it in `TOOL_REGISTRY`. The tool appears in the agent editor checkboxes immediately.

### Add a new messaging channel (e.g. Slack)

1. Create `app/channels/slack_bot.py` mirroring `telegram_bot.py`.
2. Add `"slack"` to the agent `channels` checkbox in `app/templates/agent_edit.html`.
3. In `app/main.py` lifespan, build and launch the Slack app alongside Telegram.

### Add a new workflow template

Append a new `_upsert_workflow(...)` call in `app/seed.py` and re-run `python -m app.seed`.

### Swap the LLM provider

In `app/agents/runtime.py`, replace `ChatGroq` with any LangChain chat model (`ChatAnthropic`, `ChatOpenAI`, `ChatOllama`, etc.). Update `requirements.txt` and the env var name accordingly.

---

## Project structure

```
yuno-agent-platform/
  README.md
  requirements.txt
  setup.sh / setup.bat            # single setup command
  run.sh / run.bat
  .env.example
  pytest.ini
  app/
    main.py                       # FastAPI app, lifespan, page routes
    config.py
    database.py
    models.py                     # SQLAlchemy ORM
    schemas.py                    # Pydantic schemas
    events.py                     # in-process pub/sub
    seed.py                       # seeds agents + 2 templates
    agents/
      runtime.py                  # LangGraph executor (Groq)
      tools.py                    # web_search, calculator, current_time, echo
      workflow.py                 # multi-agent orchestrator
    channels/
      telegram_bot.py
    routers/
      agents.py
      workflows.py
      runs.py
      ws.py
    templates/                    # Jinja2 HTML
    static/
  tests/
    conftest.py
    test_agents.py
    test_workflow.py
    test_tools.py
  data/                           # SQLite file lives here
```

---

## Tests

```
.\.venv\Scripts\Activate.ps1
pytest -v
```

The tests use an in-memory SQLite and mock the LangGraph runtime, so they run in about a second and need no API key.

---

## Known limitations / trade-offs

- **No multi-user auth** — single-tenant. Adding sessions/JWTs is a 2-hour follow-up.
- **In-process Telegram polling** — fine for a single-instance deployment. For HA, switch to Telegram webhooks behind a load balancer.
- **EventBus is in-process** — perfect for one Uvicorn worker. For multi-worker, swap to Redis pub/sub (the `bus.publish/subscribe` interface is intentionally narrow).
- **No vector memory** — the `memory_enabled` flag is wired through but currently controls only the LangGraph message history. Plugging in a vector store (e.g. Chroma) is straightforward via LangChain.
- **Cron schedules are informational only** — adding APScheduler would take about 30 minutes.
- **`web_search` uses DuckDuckGo HTML** and can hit rate limits on a shared IP. Swap to SerpAPI / Brave Search / Tavily for production use.

---

## License

MIT. Built for the Yuno AI Engineer Hiring Challenge.
