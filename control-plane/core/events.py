# control-plane/core/events.py
"""
Event Bus - Internal Pub/Sub for Event-Driven Architecture

Provides decoupled communication between components:
- Publishers emit events without knowing consumers
- Subscribers react to events independently
- Enables audit trail, retry, and extensibility
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
import traceback

logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """Event handler priority levels"""
    HIGH = 1      # Security, critical updates
    NORMAL = 5    # Standard operations
    LOW = 10      # Logging, analytics


@dataclass
class Event:
    """Base event class"""
    event_type: str
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: Optional[str] = None
    source: Optional[str] = None
    version: int = 1

    def __post_init__(self):
        if self.event_id is None:
            import uuid
            self.event_id = str(uuid.uuid4())

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "version": self.version
        }


@dataclass
class HandlerRegistration:
    """Registration info for an event handler"""
    handler: Callable
    priority: EventPriority
    is_async: bool
    retry_count: int = 3
    retry_delay: float = 1.0


class EventBus:
    """
    In-process Event Bus with pub/sub pattern

    Features:
    - Sync and async handlers
    - Priority-based execution order
    - Retry on failure
    - Event history for debugging
    """

    _instance: Optional['EventBus'] = None

    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._handlers: Dict[str, List[HandlerRegistration]] = {}
        self._event_history: List[Event] = []
        self._max_history_size: int = 1000
        self._initialized = True
        logger.info("EventBus initialized")

    def subscribe(
        self,
        event_type: str,
        handler: Callable,
        priority: EventPriority = EventPriority.NORMAL,
        retry_count: int = 3,
        retry_delay: float = 1.0
    ) -> None:
        """
        Subscribe a handler to an event type

        Args:
            event_type: Event type to subscribe to (e.g., "NodeRegistered")
            handler: Callable that receives Event object
            priority: Execution priority (HIGH runs first)
            retry_count: Number of retries on failure
            retry_delay: Seconds between retries
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []

        is_async = asyncio.iscoroutinefunction(handler)
        registration = HandlerRegistration(
            handler=handler,
            priority=priority,
            is_async=is_async,
            retry_count=retry_count,
            retry_delay=retry_delay
        )

        self._handlers[event_type].append(registration)
        # Sort by priority (lower number = higher priority)
        self._handlers[event_type].sort(key=lambda r: r.priority.value)

        logger.debug(f"Subscribed {handler.__name__} to {event_type} with priority {priority.name}")

    def unsubscribe(self, event_type: str, handler: Callable) -> bool:
        """Remove a handler from an event type"""
        if event_type not in self._handlers:
            return False

        original_count = len(self._handlers[event_type])
        self._handlers[event_type] = [
            r for r in self._handlers[event_type] if r.handler != handler
        ]
        return len(self._handlers[event_type]) < original_count

    def publish(self, event: Event) -> None:
        """
        Publish an event synchronously

        All handlers are executed in priority order.
        Failures are logged but don't stop other handlers.
        """
        self._add_to_history(event)
        handlers = self._handlers.get(event.event_type, [])

        if not handlers:
            logger.debug(f"No handlers for event: {event.event_type}")
            return

        logger.info(f"Publishing event: {event.event_type} (id={event.event_id})")

        for registration in handlers:
            self._execute_handler_sync(registration, event)

    async def publish_async(self, event: Event) -> None:
        """
        Publish an event asynchronously

        Async handlers run concurrently, sync handlers run in order.
        """
        self._add_to_history(event)
        handlers = self._handlers.get(event.event_type, [])

        if not handlers:
            logger.debug(f"No handlers for event: {event.event_type}")
            return

        logger.info(f"Publishing async event: {event.event_type} (id={event.event_id})")

        async_tasks = []
        for registration in handlers:
            if registration.is_async:
                task = self._execute_handler_async(registration, event)
                async_tasks.append(task)
            else:
                self._execute_handler_sync(registration, event)

        if async_tasks:
            await asyncio.gather(*async_tasks, return_exceptions=True)

    def _execute_handler_sync(self, registration: HandlerRegistration, event: Event) -> None:
        """Execute a sync handler with retry logic"""
        handler = registration.handler

        for attempt in range(registration.retry_count + 1):
            try:
                if registration.is_async:
                    # Run async handler in sync context
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Create a new task if loop is already running
                        asyncio.create_task(handler(event))
                    else:
                        loop.run_until_complete(handler(event))
                else:
                    handler(event)
                return  # Success
            except Exception as e:
                if attempt < registration.retry_count:
                    logger.warning(
                        f"Handler {handler.__name__} failed (attempt {attempt + 1}), retrying: {e}"
                    )
                    import time
                    time.sleep(registration.retry_delay)
                else:
                    logger.error(
                        f"Handler {handler.__name__} failed after {registration.retry_count + 1} attempts: {e}\n"
                        f"{traceback.format_exc()}"
                    )

    async def _execute_handler_async(self, registration: HandlerRegistration, event: Event) -> None:
        """Execute an async handler with retry logic"""
        handler = registration.handler

        for attempt in range(registration.retry_count + 1):
            try:
                await handler(event)
                return  # Success
            except Exception as e:
                if attempt < registration.retry_count:
                    logger.warning(
                        f"Async handler {handler.__name__} failed (attempt {attempt + 1}), retrying: {e}"
                    )
                    await asyncio.sleep(registration.retry_delay)
                else:
                    logger.error(
                        f"Async handler {handler.__name__} failed after {registration.retry_count + 1} attempts: {e}\n"
                        f"{traceback.format_exc()}"
                    )

    def _add_to_history(self, event: Event) -> None:
        """Add event to history, maintaining max size"""
        self._event_history.append(event)
        if len(self._event_history) > self._max_history_size:
            self._event_history = self._event_history[-self._max_history_size:]

    def get_history(self, event_type: Optional[str] = None, limit: int = 100) -> List[Event]:
        """Get recent events, optionally filtered by type"""
        history = self._event_history
        if event_type:
            history = [e for e in history if e.event_type == event_type]
        return history[-limit:]

    def get_subscriptions(self) -> Dict[str, int]:
        """Get count of handlers per event type"""
        return {event_type: len(handlers) for event_type, handlers in self._handlers.items()}

    def clear(self) -> None:
        """Clear all subscriptions and history (for testing)"""
        self._handlers.clear()
        self._event_history.clear()


# Decorator for subscribing handlers
def event_handler(
    event_type: str,
    priority: EventPriority = EventPriority.NORMAL,
    retry_count: int = 3
):
    """
    Decorator to register a function as an event handler

    Usage:
        @event_handler("NodeRegistered")
        def on_node_registered(event: Event):
            print(f"Node registered: {event.payload}")
    """
    def decorator(func: Callable) -> Callable:
        # Register with the singleton EventBus
        event_bus.subscribe(event_type, func, priority, retry_count)

        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Singleton instance
event_bus = EventBus()


# Convenience functions
def publish(event_type: str, payload: Dict[str, Any], source: Optional[str] = None) -> Event:
    """
    Convenience function to create and publish an event

    Usage:
        publish("NodeRegistered", {"node_id": 1, "hostname": "web-01"})
    """
    event = Event(event_type=event_type, payload=payload, source=source)
    event_bus.publish(event)
    return event


async def publish_async(event_type: str, payload: Dict[str, Any], source: Optional[str] = None) -> Event:
    """Async version of publish"""
    event = Event(event_type=event_type, payload=payload, source=source)
    await event_bus.publish_async(event)
    return event
