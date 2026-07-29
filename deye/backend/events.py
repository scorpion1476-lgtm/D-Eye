"""Event-driven workflows layered over `deye.backend.Queue`.

Callers register a subscriber for a topic; each `enqueue_and_dispatch`
call transactionally enqueues a job and immediately drives synchronous
subscribers. Async/threaded dispatch is intentionally out of scope of
core (queue-based deferral is the async path).

Category 10 row: C10-F005 event-driven workflows.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

from deye.backend import Queue


@dataclass
class EventBus:
    """In-process synchronous event bus that persists via Queue.

    - `subscribe(topic, handler)` adds a handler (idempotent by identity).
    - `dispatch(topic, payload, tenant)` runs every handler synchronously
      and returns their results. Every dispatch also persists a queue
      job so a downstream async worker can re-play (audit + replay).
    """

    queue: Queue
    subscribers: dict[str, list[Callable[[dict], object]]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def subscribe(self, topic: str, handler: Callable[[dict], object]) -> None:
        if handler not in self.subscribers[topic]:
            self.subscribers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Callable[[dict], object]) -> None:
        if handler in self.subscribers.get(topic, []):
            self.subscribers[topic].remove(handler)

    def dispatch(self, topic: str, payload: dict, *,
                 tenant: str = "default") -> dict:
        job_id = self.queue.enqueue(topic, payload, tenant=tenant)
        results: list[object] = []
        errors: list[str] = []
        for handler in list(self.subscribers.get(topic, [])):
            try:
                results.append(handler(payload))
            except Exception as exc:  # noqa: BLE001 -- record + continue
                errors.append(f"{handler.__name__}: {exc}")
        self.queue.complete(job_id, error=("; ".join(errors) if errors else None))
        return {
            "job_id": job_id, "topic": topic,
            "subscriber_count": len(self.subscribers.get(topic, [])),
            "results": results, "errors": errors,
        }
