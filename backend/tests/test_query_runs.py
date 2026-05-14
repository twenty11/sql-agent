import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import query_runs


class FakeRedis:
    def __init__(self):
        self.hashes = {}
        self.streams = {}

    async def hset(self, key, mapping):
        self.hashes.setdefault(key, {}).update(mapping)

    async def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    async def hget(self, key, field):
        return self.hashes.get(key, {}).get(field)

    async def expire(self, key, seconds):
        return True

    async def xadd(self, key, fields):
        event_id = f"{len(self.streams.get(key, [])) + 1}-0"
        self.streams.setdefault(key, []).append((event_id, fields))
        return event_id

    async def xread(self, streams, count=None, block=None):
        key, after_id = next(iter(streams.items()))
        after_seq = int(after_id.split("-", 1)[0])
        entries = [
            (event_id, fields)
            for event_id, fields in self.streams.get(key, [])
            if int(event_id.split("-", 1)[0]) > after_seq
        ]
        if count is not None:
            entries = entries[:count]
        return [(key, entries)] if entries else []


class FakeMessage:
    def __init__(self, *, metadata, created_at=None, content=""):
        self.id = "m1"
        self.role = "assistant"
        self.content = content
        self.metadata_ = metadata
        self.created_at = created_at or datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_reconcile_preserves_active_streaming_run(monkeypatch):
    redis = FakeRedis()
    await query_runs.create_run(
        redis,
        run_id="r1",
        user_id="u1",
        session_id="s1",
        message_id="m1",
    )
    await query_runs.append_event(redis, "r1", {"type": "answer_chunk", "content": "hi"}, progress=True)
    message = FakeMessage(metadata={"status": "streaming", "run_id": "r1", "last_event_id": "0-0"})
    calls = []
    monkeypatch.setattr(
        "db.crud.messages.update_assistant_message_if_streaming_sync",
        lambda *args: calls.append(args) or True,
    )

    result = await query_runs.reconcile_streaming_messages(redis, [message])

    assert result[0].metadata_["status"] == "streaming"
    assert result[0].metadata_["last_event_id"] == "1-0"
    assert result[0].content == "hi"
    assert calls == []


@pytest.mark.asyncio
async def test_reconcile_replays_only_events_after_persisted_offset(monkeypatch):
    redis = FakeRedis()
    await query_runs.create_run(
        redis,
        run_id="r1",
        user_id="u1",
        session_id="s1",
        message_id="m1",
    )
    await query_runs.append_event(redis, "r1", {"type": "answer_chunk", "content": "hello"}, progress=True)
    await query_runs.append_event(redis, "r1", {"type": "answer_chunk", "content": " world"}, progress=True)
    message = FakeMessage(
        content="hello",
        metadata={"status": "streaming", "run_id": "r1", "last_event_id": "1-0"},
    )
    calls = []
    monkeypatch.setattr(
        "db.crud.messages.update_assistant_message_if_streaming_sync",
        lambda *args: calls.append(args) or True,
    )

    result = await query_runs.reconcile_streaming_messages(redis, [message])

    assert result[0].content == "hello world"
    assert result[0].metadata_["status"] == "streaming"
    assert result[0].metadata_["last_event_id"] == "2-0"
    assert calls == []


@pytest.mark.asyncio
async def test_reconcile_replays_terminal_event_and_persists_terminal_metadata(monkeypatch):
    redis = FakeRedis()
    await query_runs.create_run(
        redis,
        run_id="r1",
        user_id="u1",
        session_id="s1",
        message_id="m1",
    )
    await query_runs.append_event(redis, "r1", {"type": "answer_chunk", "content": "partial"}, progress=True)
    await query_runs.append_event(
        redis,
        "r1",
        {"type": "done", "state": {"final_answer": "final", "generated_sql": "select 1"}},
    )
    message = FakeMessage(metadata={"status": "streaming", "run_id": "r1", "last_event_id": "0-0"})
    calls = []
    monkeypatch.setattr(
        "db.crud.messages.update_assistant_message_if_streaming_sync",
        lambda *args: calls.append(args) or True,
    )

    result = await query_runs.reconcile_streaming_messages(redis, [message])

    assert result[0].content == "final"
    assert result[0].metadata_["status"] == "completed"
    assert result[0].metadata_["last_event_id"] == "2-0"
    assert result[0].metadata_["sql"] == "select 1"
    assert calls


@pytest.mark.asyncio
async def test_reconcile_marks_missing_run_failed(monkeypatch):
    redis = FakeRedis()
    message = FakeMessage(
        metadata={"status": "streaming", "run_id": "missing"},
        created_at=datetime.now(timezone.utc) - timedelta(seconds=query_runs.MISSING_RUN_GRACE_SECONDS + 1),
    )
    calls = []
    monkeypatch.setattr(
        "db.crud.messages.update_assistant_message_if_streaming_sync",
        lambda *args: calls.append(args) or True,
    )

    await query_runs.reconcile_streaming_messages(redis, [message])

    assert message.metadata_["status"] == "failed"
    assert "no longer available" in message.metadata_["error"]
    assert calls


@pytest.mark.asyncio
async def test_reconcile_marks_stale_heartbeat_failed(monkeypatch):
    redis = FakeRedis()
    await query_runs.create_run(
        redis,
        run_id="r1",
        user_id="u1",
        session_id="s1",
        message_id="m1",
    )
    stale = datetime.now(timezone.utc) - timedelta(seconds=query_runs.HEARTBEAT_STALE_SECONDS + 1)
    await redis.hset(query_runs.run_key("r1"), mapping={"last_heartbeat": stale.isoformat()})
    message = FakeMessage(metadata={"status": "streaming", "run_id": "r1"})
    calls = []
    monkeypatch.setattr(
        "db.crud.messages.update_assistant_message_if_streaming_sync",
        lambda *args: calls.append(args) or True,
    )

    await query_runs.reconcile_streaming_messages(redis, [message])

    assert message.metadata_["status"] == "failed"
    assert "stopped responding" in message.metadata_["error"]
    assert calls


@pytest.mark.asyncio
async def test_stream_events_replays_from_offset_and_stops_on_terminal():
    redis = FakeRedis()
    await query_runs.create_run(
        redis,
        run_id="r1",
        user_id="u1",
        session_id="s1",
        message_id="m1",
    )
    await query_runs.append_event(redis, "r1", {"type": "answer_chunk", "content": "a"})
    await query_runs.append_event(redis, "r1", {"type": "answer_chunk", "content": "b"})
    await query_runs.append_event(redis, "r1", {"type": "done", "state": {}})

    events = []
    async for event_id, payload in query_runs.stream_events(redis, "r1", "1-0"):
        events.append((event_id, payload))

    assert [event_id for event_id, _payload in events] == ["2-0", "3-0"]
    assert events[-1][1]["type"] == "done"


@pytest.mark.asyncio
async def test_stream_events_emits_error_when_streaming_run_heartbeat_is_stale():
    redis = FakeRedis()
    await query_runs.create_run(
        redis,
        run_id="r1",
        user_id="u1",
        session_id="s1",
        message_id="m1",
    )
    stale = datetime.now(timezone.utc) - timedelta(seconds=query_runs.HEARTBEAT_STALE_SECONDS + 1)
    await redis.hset(query_runs.run_key("r1"), mapping={"last_heartbeat": stale.isoformat()})

    events = []
    async for event_id, payload in query_runs.stream_events(redis, "r1", "0-0"):
        events.append((event_id, payload))

    run = await query_runs.get_run(redis, "r1")
    assert len(events) == 1
    assert events[0][1] == {"type": "error", "content": "Query stopped responding."}
    assert run["status"] == "failed"
    assert run["error"] == "Query stopped responding."
