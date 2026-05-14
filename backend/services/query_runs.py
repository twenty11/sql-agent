"""Redis-backed query run registry and resumable SSE event storage."""

from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import redis as sync_redis
import redis.asyncio as aioredis

from config import get_settings

RUN_TTL_SECONDS = 2 * 60 * 60
STREAM_TTL_SECONDS = 2 * 60 * 60
HEARTBEAT_INTERVAL_SECONDS = 15
HEARTBEAT_STALE_SECONDS = 75
ABSOLUTE_TIMEOUT_SECONDS = 30 * 60
MISSING_RUN_GRACE_SECONDS = 15
STREAM_BLOCK_MS = 5000
STREAM_READ_COUNT = 50
PARTIAL_FLUSH_SECONDS = 2
PARTIAL_FLUSH_CHARS = 500
TERMINAL_STATUSES = {"completed", "failed", "stopped"}
TERMINAL_EVENT_TYPES = {"done", "error", "stopped"}

_sync_redis_client: sync_redis.Redis | None = None
_sync_redis_lock = threading.Lock()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def run_key(run_id: str) -> str:
    return f"query:run:{run_id}"


def events_key(run_id: str) -> str:
    return f"query:run:{run_id}:events"


def terminal_status_for_event(payload: dict[str, Any]) -> str | None:
    event_type = payload.get("type")
    if event_type == "done":
        return "completed"
    if event_type == "error":
        return "failed"
    if event_type == "stopped":
        return "stopped"
    return None


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_loads(value: str) -> dict[str, Any]:
    loaded = json.loads(value)
    return loaded if isinstance(loaded, dict) else {"type": "message", "content": loaded}


def _normalize_entry(entry: Any) -> tuple[str, dict[str, Any]]:
    event_id, fields = entry
    payload = fields.get("payload", "{}")
    return event_id, _json_loads(payload)


async def create_run(
    redis: aioredis.Redis,
    *,
    run_id: str,
    user_id: str,
    session_id: str,
    message_id: str,
) -> dict[str, str]:
    now = iso_now()
    data = {
        "run_id": run_id,
        "user_id": user_id,
        "session_id": session_id,
        "message_id": message_id,
        "status": "streaming",
        "started_at": now,
        "last_heartbeat": now,
        "last_progress_at": now,
        "last_event_id": "0-0",
        "cancel_requested": "0",
    }
    await redis.hset(run_key(run_id), mapping=data)
    await redis.expire(run_key(run_id), RUN_TTL_SECONDS)
    return data


async def get_run(redis: aioredis.Redis, run_id: str) -> dict[str, str] | None:
    data = await redis.hgetall(run_key(run_id))
    return data or None


async def touch_heartbeat(redis: aioredis.Redis, run_id: str) -> None:
    now = iso_now()
    await redis.hset(run_key(run_id), mapping={"last_heartbeat": now})
    await redis.expire(run_key(run_id), RUN_TTL_SECONDS)


async def append_event(
    redis: aioredis.Redis,
    run_id: str,
    payload: dict[str, Any],
    *,
    progress: bool = False,
) -> str:
    event_id = await redis.xadd(events_key(run_id), {"payload": _json_dumps(payload)})
    now = iso_now()
    patch: dict[str, str] = {
        "last_event_id": event_id,
        "last_heartbeat": now,
    }
    if progress:
        patch["last_progress_at"] = now
    terminal_status = terminal_status_for_event(payload)
    if terminal_status:
        patch["status"] = terminal_status
        patch["finished_at"] = now
        if terminal_status == "failed":
            patch["error"] = str(payload.get("content") or "Query run failed.")
    await redis.hset(run_key(run_id), mapping=patch)
    await redis.expire(run_key(run_id), RUN_TTL_SECONDS)
    await redis.expire(events_key(run_id), STREAM_TTL_SECONDS)
    return event_id


async def read_run_events(
    redis: aioredis.Redis,
    run_id: str,
    after_event_id: str,
    *,
    block_ms: int | None = STREAM_BLOCK_MS,
    count: int = STREAM_READ_COUNT,
) -> list[tuple[str, dict[str, Any]]]:
    rows = await redis.xread({events_key(run_id): after_event_id}, count=count, block=block_ms)
    if not rows:
        return []
    _stream_name, entries = rows[0]
    return [_normalize_entry(entry) for entry in entries]


def _state_metadata_patch(state: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    if state.get("generated_sql") is not None:
        patch["sql"] = state.get("generated_sql")
    if state.get("query_explanation") is not None:
        patch["explanation"] = state.get("query_explanation")
    if state.get("execution_result") is not None:
        patch["result"] = state.get("execution_result")
    if state.get("intent_type") is not None:
        patch["intent_type"] = state.get("intent_type")
    if state.get("referenced_result_ids") is not None:
        patch["referenced_result_ids"] = state.get("referenced_result_ids")
    if state.get("query_result_id") is not None:
        patch["query_result_id"] = state.get("query_result_id")
    return patch


def _apply_replayed_event(
    content: str,
    metadata: dict[str, Any],
    event_id: str,
    payload: dict[str, Any],
) -> tuple[str, dict[str, Any], bool]:
    metadata = dict(metadata)
    metadata["last_event_id"] = event_id
    event_type = payload.get("type")

    if event_type == "answer_chunk":
        content += payload.get("content") or ""
        metadata["status"] = "streaming"
        return content, metadata, False

    if event_type == "explanation":
        metadata["explanation"] = payload.get("content")
        return content, metadata, False

    if event_type == "result":
        metadata["result"] = payload.get("data")
        return content, metadata, False

    if event_type == "done":
        state = payload.get("state") or {}
        metadata.update(_state_metadata_patch(state))
        metadata["status"] = "completed"
        metadata["finished_at"] = metadata.get("finished_at") or iso_now()
        if state.get("final_answer"):
            content = state["final_answer"]
        return content, metadata, True

    if event_type == "stopped":
        state = payload.get("state") or {}
        metadata.update(_state_metadata_patch(state))
        metadata["status"] = "stopped"
        metadata["finished_at"] = metadata.get("finished_at") or iso_now()
        metadata["stopped_at"] = metadata.get("stopped_at") or iso_now()
        if state.get("final_answer"):
            content = state["final_answer"]
        return content, metadata, True

    if event_type == "error":
        error = str(payload.get("content") or "Query run failed.")
        metadata["status"] = "failed"
        metadata["error"] = error
        metadata["finished_at"] = metadata.get("finished_at") or iso_now()
        content = content or error
        return content, metadata, True

    return content, metadata, False


async def _replay_available_events(
    redis: aioredis.Redis,
    run_id: str,
    content: str,
    metadata: dict[str, Any],
) -> tuple[str, dict[str, Any], bool]:
    last_event_id = metadata.get("last_event_id") or "0-0"
    terminal_seen = False
    while True:
        entries = await read_run_events(redis, run_id, last_event_id, block_ms=None)
        if not entries:
            return content, metadata, terminal_seen
        for event_id, payload in entries:
            content, metadata, terminal_seen = _apply_replayed_event(content, metadata, event_id, payload)
            last_event_id = event_id
            if terminal_seen:
                return content, metadata, True


async def request_cancel(redis: aioredis.Redis, run_id: str, reason: str = "user_cancelled") -> None:
    await redis.hset(
        run_key(run_id),
        mapping={
            "cancel_requested": "1",
            "cancel_reason": reason,
            "last_heartbeat": iso_now(),
        },
    )
    await redis.expire(run_key(run_id), RUN_TTL_SECONDS)


async def is_cancel_requested(redis: aioredis.Redis, run_id: str) -> bool:
    return (await redis.hget(run_key(run_id), "cancel_requested")) == "1"


def _get_sync_redis() -> sync_redis.Redis:
    global _sync_redis_client
    if _sync_redis_client is None:
        with _sync_redis_lock:
            if _sync_redis_client is None:
                _sync_redis_client = sync_redis.from_url(
                    get_settings().redis_url,
                    decode_responses=True,
                )
    return _sync_redis_client


def is_cancel_requested_sync(run_id: str) -> bool:
    try:
        return _get_sync_redis().hget(run_key(run_id), "cancel_requested") == "1"
    except Exception:
        return False


def run_has_stale_heartbeat(run: dict[str, str], now: datetime | None = None) -> bool:
    heartbeat = parse_datetime(run.get("last_heartbeat"))
    if not heartbeat:
        return True
    now = now or utc_now()
    return (now - heartbeat).total_seconds() > HEARTBEAT_STALE_SECONDS


def run_has_absolute_timeout(run: dict[str, str], now: datetime | None = None) -> bool:
    started = parse_datetime(run.get("started_at"))
    if not started:
        return False
    now = now or utc_now()
    return (now - started).total_seconds() > ABSOLUTE_TIMEOUT_SECONDS


def missing_run_grace_elapsed(created_at: datetime, now: datetime | None = None) -> bool:
    created = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    now = now or utc_now()
    return (now - created).total_seconds() > MISSING_RUN_GRACE_SECONDS


async def stream_events(
    redis: aioredis.Redis,
    run_id: str,
    from_event_id: str | None = None,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    last_event_id = from_event_id or "0-0"
    while True:
        entries = await read_run_events(redis, run_id, last_event_id)
        if not entries:
            run = await get_run(redis, run_id)
            if not run or run.get("status") in TERMINAL_STATUSES:
                break
            failure_reason = None
            if run_has_absolute_timeout(run):
                await request_cancel(redis, run_id, "absolute_timeout")
                failure_reason = "Query exceeded the maximum runtime."
            elif run_has_stale_heartbeat(run):
                failure_reason = "Query stopped responding."
            if failure_reason:
                event_id = await append_event(
                    redis,
                    run_id,
                    {"type": "error", "content": failure_reason},
                    progress=True,
                )
                yield event_id, {"type": "error", "content": failure_reason}
                return
            continue
        for event_id, payload in entries:
            last_event_id = event_id
            yield event_id, payload
            if payload.get("type") in TERMINAL_EVENT_TYPES:
                return


async def reconcile_streaming_messages(redis: aioredis.Redis, messages: list[Any]) -> list[Any]:
    from db.crud.messages import update_assistant_message_if_streaming_sync

    now = utc_now()
    for message in messages:
        metadata = dict(message.metadata_ or {})
        if message.role != "assistant" or metadata.get("status") != "streaming":
            continue

        run_id = metadata.get("run_id")
        failure_reason: str | None = None
        content = message.content or ""
        if not run_id:
            failure_reason = "Query run metadata is missing."
        else:
            run = await get_run(redis, run_id)
            if not run:
                if missing_run_grace_elapsed(message.created_at, now):
                    failure_reason = "Query run is no longer available."
            else:
                content, metadata, replayed_terminal = await _replay_available_events(
                    redis,
                    run_id,
                    content,
                    metadata,
                )
                message.content = content
                message.metadata_ = metadata
                if replayed_terminal:
                    updated = await asyncio.to_thread(
                        update_assistant_message_if_streaming_sync,
                        message.id,
                        content,
                        metadata,
                    )
                    if updated:
                        message.content = content
                        message.metadata_ = metadata
                    continue

            if run and run.get("status") in TERMINAL_STATUSES:
                terminal_status = run.get("status") or "failed"
                metadata.update({
                    "status": terminal_status,
                    "last_event_id": run.get("last_event_id") or metadata.get("last_event_id"),
                    "last_heartbeat": run.get("last_heartbeat") or metadata.get("last_heartbeat"),
                    "started_at": run.get("started_at") or metadata.get("started_at"),
                    "finished_at": run.get("finished_at") or iso_now(),
                })
                if terminal_status == "failed":
                    metadata["error"] = metadata.get("error") or run.get("error") or "Query run failed."
                if terminal_status == "stopped":
                    metadata["stopped_at"] = metadata.get("stopped_at") or iso_now()
                content = content or metadata.get("error") or ""
                await asyncio.to_thread(
                    update_assistant_message_if_streaming_sync,
                    message.id,
                    content,
                    metadata,
                )
                message.content = content
                message.metadata_ = metadata
            elif run and run_has_absolute_timeout(run, now):
                await request_cancel(redis, run_id, "absolute_timeout")
                failure_reason = "Query exceeded the maximum runtime."
            elif run and run_has_stale_heartbeat(run, now):
                failure_reason = "Query stopped responding."
            elif run:
                metadata.update({
                    "last_heartbeat": run.get("last_heartbeat") or metadata.get("last_heartbeat"),
                    "started_at": run.get("started_at") or metadata.get("started_at"),
                })
                message.content = content
                message.metadata_ = metadata
                continue

        if not failure_reason:
            continue
        metadata.update({
            "status": "failed",
            "error": failure_reason,
            "finished_at": iso_now(),
        })
        await asyncio.to_thread(
            update_assistant_message_if_streaming_sync,
            message.id,
            content or failure_reason,
            metadata,
        )
        message.content = content or failure_reason
        message.metadata_ = metadata
    return messages
