"""Redis progress publication, with identical local fallback semantics (§4.3)."""

import json
from threading import Lock
from queue import Queue
from typing import Any

from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from app.core.settings import settings

_last: dict[str, dict[str, Any]] = {}
_cancelled: set[str] = set()
_lock = Lock()
_subscribers: dict[str, list[Queue]] = {}


def redis_client() -> Redis:
    return Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=0.1,
        socket_timeout=0.25,
        retry=Retry(NoBackoff(), 0),
    )


def publish(audit_id: str, event: str, data: dict[str, Any]) -> None:
    message = {"event": event, "data": data}
    with _lock:
        _last[audit_id] = message
        for queue in _subscribers.get(audit_id, []):
            queue.put(message)
    if settings.job_mode == "rq":
        client = redis_client()
        wire = json.dumps(message)
        client.setex(f"audit:{audit_id}:last", 86400, wire)
        client.publish(f"audit:{audit_id}", wire)


def last(audit_id: str) -> dict[str, Any] | None:
    if settings.job_mode == "rq":
        value = redis_client().get(f"audit:{audit_id}:last")
        return json.loads(value) if value else None
    with _lock:
        return _last.get(audit_id)


def cancel(audit_id: str) -> None:
    with _lock:
        _cancelled.add(audit_id)
    if settings.job_mode == "rq":
        redis_client().setex(f"audit:{audit_id}:cancel", 3600, "1")


def is_cancelled(audit_id: str) -> bool:
    if settings.job_mode == "rq":
        return bool(redis_client().exists(f"audit:{audit_id}:cancel"))
    with _lock:
        return audit_id in _cancelled


def subscribe(audit_id: str) -> Queue:
    queue: Queue = Queue()
    with _lock:
        _subscribers.setdefault(audit_id, []).append(queue)
    return queue


def unsubscribe(audit_id: str, queue: Queue) -> None:
    with _lock:
        if queue in _subscribers.get(audit_id, []):
            _subscribers[audit_id].remove(queue)
        if not _subscribers.get(audit_id):
            _subscribers.pop(audit_id, None)
