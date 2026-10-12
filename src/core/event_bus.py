"""Typed event bus — asyncio.Queue with typed events.

All inter-component communication goes through this bus.
Only typed events are allowed — no raw dicts.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

logger = logging.getLogger(__name__)


class EventType(Enum):
    """All event types in the system."""

    # Health events
    HEALTH_SNAPSHOT = auto()
    FPS_UPDATE = auto()
    THERMAL_UPDATE = auto()
    MEMORY_UPDATE = auto()
    THROTTLE_UPDATE = auto()

    # System events
    MODEL_LOADED = auto()
    PIPELINE_STARTED = auto()
    PIPELINE_STOPPED = auto()
    SHUTDOWN = auto()


@dataclass(frozen=True, slots=True)
class Event:
    """Single typed event on the bus."""

    type: EventType
    data: Any = None
    source: str = ""


class EventBus:
    """Simple async event bus backed by asyncio.Queue.

    Consumers call get() to receive events.
    Producers call put() to publish events.
    """

    def __init__(self, maxsize: int = 256):
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=maxsize)

    async def put(self, event: Event) -> None:
        """Publish an event. Drops if queue is full (non-blocking)."""
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("Event bus full, dropping event: %s", event.type.name)

    async def get(self) -> Event:
        """Wait for the next event."""
        return await self._queue.get()

    def get_nowait(self) -> Event | None:
        """Get an event without waiting. Returns None if empty."""
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    @property
    def qsize(self) -> int:
        return self._queue.qsize()
