"""In-process pub/sub for live monitoring (used by the WebSocket monitor)."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Set


class EventBus:
    """Tiny async pub/sub. Subscribers get every event as a JSON-serialisable dict."""

    def __init__(self) -> None:
        self._subscribers: Set[asyncio.Queue] = set()

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def publish(self, event: dict[str, Any]) -> None:
        """Fire-and-forget publish. Drops events for slow subscribers instead of blocking."""
        event = {"ts": datetime.utcnow().isoformat(), **event}
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # subscriber is slow — drop this event for them
                pass


bus = EventBus()


def emit(event_type: str, **kwargs: Any) -> None:
    """Convenience for publishing typed events."""
    bus.publish({"type": event_type, **kwargs})
