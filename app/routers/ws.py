"""WebSocket endpoint for live monitoring."""
from __future__ import annotations

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.events import bus

router = APIRouter()


@router.websocket("/ws/monitor")
async def monitor_ws(ws: WebSocket):
    """Stream every event from the in-process bus to the connected browser."""
    await ws.accept()
    queue = await bus.subscribe()
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
                await ws.send_json(event)
            except asyncio.TimeoutError:
                # keepalive ping
                await ws.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(queue)
