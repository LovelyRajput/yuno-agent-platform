"""FastAPI entry point. Wires routers, mounts static UI, starts Telegram bot."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import init_db, get_db
from app import models
from app.config import has_groq_key, has_telegram_token
from app.routers import agents as agents_router
from app.routers import workflows as workflows_router
from app.routers import runs as runs_router
from app.routers import ws as ws_router
from app.channels.telegram_bot import build_application, run_polling_in_background

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("main")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log.info("Database ready.")
    log.info("Groq key present: %s", has_groq_key())
    log.info("Telegram token present: %s", has_telegram_token())

    # Start Telegram bot (if token present)
    bot_task = None
    bot_app = build_application()
    if bot_app:
        bot_task = asyncio.create_task(run_polling_in_background(bot_app))
        log.info("Telegram bot starting in background.")
    else:
        log.warning("Telegram bot NOT starting — set TELEGRAM_BOT_TOKEN to enable.")

    yield

    if bot_task:
        bot_task.cancel()
        try:
            await bot_task
        except Exception:
            pass


app = FastAPI(
    title="Yuno AI Agent Orchestration Platform",
    description="Create AI agents, configure them, connect them into workflows, "
                "talk to them on Telegram.",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount static + routers
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.include_router(agents_router.router)
app.include_router(workflows_router.router)
app.include_router(runs_router.router)
app.include_router(ws_router.router)


# ---------- HTML pages (server-rendered shells; JS does the dynamic work) ----------

def _ctx(request: Request, **extra) -> dict:
    return {
        "request": request,
        "anthropic_ok": has_groq_key(),
        "telegram_ok": has_telegram_token(),
        **extra,
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    agent_count = db.query(models.Agent).count()
    workflow_count = db.query(models.Workflow).count()
    run_count = db.query(models.Run).count()
    return templates.TemplateResponse(
        "index.html",
        _ctx(request, agent_count=agent_count, workflow_count=workflow_count, run_count=run_count),
    )


@app.get("/agents", response_class=HTMLResponse)
def agents_page(request: Request):
    return templates.TemplateResponse("agents.html", _ctx(request))


@app.get("/agents/new", response_class=HTMLResponse)
def agent_new_page(request: Request):
    return templates.TemplateResponse("agent_edit.html", _ctx(request, agent_id=None))


@app.get("/agents/{agent_id}/edit", response_class=HTMLResponse)
def agent_edit_page(request: Request, agent_id: int):
    return templates.TemplateResponse("agent_edit.html", _ctx(request, agent_id=agent_id))


@app.get("/workflows", response_class=HTMLResponse)
def workflows_page(request: Request):
    return templates.TemplateResponse("workflows.html", _ctx(request))


@app.get("/workflows/new", response_class=HTMLResponse)
def workflow_new_page(request: Request):
    return templates.TemplateResponse("workflow_edit.html", _ctx(request, workflow_id=None))


@app.get("/workflows/{workflow_id}/edit", response_class=HTMLResponse)
def workflow_edit_page(request: Request, workflow_id: int):
    return templates.TemplateResponse("workflow_edit.html", _ctx(request, workflow_id=workflow_id))


@app.get("/runs", response_class=HTMLResponse)
def runs_page(request: Request):
    return templates.TemplateResponse("runs.html", _ctx(request))


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail_page(request: Request, run_id: int):
    return templates.TemplateResponse("run_detail.html", _ctx(request, run_id=run_id))


@app.get("/monitor", response_class=HTMLResponse)
def monitor_page(request: Request):
    return templates.TemplateResponse("monitor.html", _ctx(request))


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
