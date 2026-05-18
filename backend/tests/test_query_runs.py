import sys
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import query_runs


class FakeRedis:
    def __init__(self):
        self.hashes = {}
        self.streams = {}
        self.strings = {}
        self.sorted_sets = {}

    def _exists(self, key):
        return (
            key in self.hashes
            or key in self.streams
            or key in self.strings
            or key in self.sorted_sets
        )

    async def set(self, key, value, ex=None, nx=False):
        if nx and self._exists(key):
            return None
        self.strings[key] = value
        return True

    async def exists(self, key):
        return 1 if self._exists(key) else 0

    async def delete(self, *keys):
        deleted = 0
        for key in keys:
            existed = self._exists(key)
            self.hashes.pop(key, None)
            self.streams.pop(key, None)
            self.strings.pop(key, None)
            self.sorted_sets.pop(key, None)
            if existed:
                deleted += 1
        return deleted

    async def hset(self, key, mapping):
        self.hashes.setdefault(key, {}).update(mapping)

    async def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    async def hget(self, key, field):
        return self.hashes.get(key, {}).get(field)

    async def expire(self, key, seconds):
        return True

    async def zremrangebyscore(self, key, min_score, max_score):
        items = self.sorted_sets.setdefault(key, {})
        max_value = float("inf") if max_score == "+inf" else float(max_score)
        min_value = float("-inf") if min_score == "-inf" else float(min_score)
        removed = [member for member, score in items.items() if min_value <= score <= max_value]
        for member in removed:
            items.pop(member, None)
        return len(removed)

    async def zscore(self, key, member):
        return self.sorted_sets.get(key, {}).get(member)

    async def zadd(self, key, mapping):
        items = self.sorted_sets.setdefault(key, {})
        for member, score in mapping.items():
            items[member] = float(score)
        return len(mapping)

    async def zrem(self, key, member):
        items = self.sorted_sets.setdefault(key, {})
        existed = member in items
        items.pop(member, None)
        return 1 if existed else 0

    async def eval(self, _script, numkeys, *args):
        keys = args[:numkeys]
        argv = args[numkeys:]
        global_key, user_key = keys
        now_ms = int(argv[0])
        ttl_ms = int(argv[1])
        run_id = argv[2]
        global_limit = int(argv[3])
        user_limit = int(argv[4])

        await self.zremrangebyscore(global_key, "-inf", now_ms)
        await self.zremrangebyscore(user_key, "-inf", now_ms)
        if await self.zscore(global_key, run_id) is not None or await self.zscore(user_key, run_id) is not None:
            return -2
        if global_limit > 0 and len(self.sorted_sets.get(global_key, {})) >= global_limit:
            return 0
        if user_limit > 0 and len(self.sorted_sets.get(user_key, {})) >= user_limit:
            return -1

        expires_at = now_ms + ttl_ms
        if global_limit > 0:
            await self.zadd(global_key, {run_id: expires_at})
        if user_limit > 0:
            await self.zadd(user_key, {run_id: expires_at})
        return 1

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


@pytest.mark.asyncio
async def test_query_capacity_rejects_when_global_limit_is_reached():
    redis = FakeRedis()

    first = await query_runs.acquire_query_capacity(
        redis,
        "r1",
        "u1",
        global_limit=1,
        user_limit=0,
        lease_ttl_seconds=120,
    )
    second = await query_runs.acquire_query_capacity(
        redis,
        "r2",
        "u2",
        global_limit=1,
        user_limit=0,
        lease_ttl_seconds=120,
    )

    assert first == query_runs.QUERY_CAPACITY_OK
    assert second == query_runs.QUERY_CAPACITY_GLOBAL_LIMIT


@pytest.mark.asyncio
async def test_query_capacity_rejects_same_user_but_allows_other_users():
    redis = FakeRedis()

    first = await query_runs.acquire_query_capacity(
        redis,
        "r1",
        "u1",
        global_limit=0,
        user_limit=1,
        lease_ttl_seconds=120,
    )
    same_user = await query_runs.acquire_query_capacity(
        redis,
        "r2",
        "u1",
        global_limit=0,
        user_limit=1,
        lease_ttl_seconds=120,
    )
    other_user = await query_runs.acquire_query_capacity(
        redis,
        "r3",
        "u2",
        global_limit=0,
        user_limit=1,
        lease_ttl_seconds=120,
    )

    assert first == query_runs.QUERY_CAPACITY_OK
    assert same_user == query_runs.QUERY_CAPACITY_USER_LIMIT
    assert other_user == query_runs.QUERY_CAPACITY_OK


@pytest.mark.asyncio
async def test_query_capacity_release_allows_new_run_for_user():
    redis = FakeRedis()
    await query_runs.acquire_query_capacity(
        redis,
        "r1",
        "u1",
        global_limit=0,
        user_limit=1,
        lease_ttl_seconds=120,
    )

    blocked = await query_runs.acquire_query_capacity(
        redis,
        "r2",
        "u1",
        global_limit=0,
        user_limit=1,
        lease_ttl_seconds=120,
    )
    await query_runs.release_query_capacity(redis, "r1", "u1")
    allowed = await query_runs.acquire_query_capacity(
        redis,
        "r2",
        "u1",
        global_limit=0,
        user_limit=1,
        lease_ttl_seconds=120,
    )

    assert blocked == query_runs.QUERY_CAPACITY_USER_LIMIT
    assert allowed == query_runs.QUERY_CAPACITY_OK


@pytest.mark.asyncio
async def test_query_capacity_expired_lease_is_cleaned_up(monkeypatch):
    redis = FakeRedis()
    now = 100_000
    monkeypatch.setattr(query_runs, "_unix_ms", lambda: now)
    await query_runs.acquire_query_capacity(
        redis,
        "r1",
        "u1",
        global_limit=0,
        user_limit=1,
        lease_ttl_seconds=1,
    )

    monkeypatch.setattr(query_runs, "_unix_ms", lambda: now + 1001)
    result = await query_runs.acquire_query_capacity(
        redis,
        "r2",
        "u1",
        global_limit=0,
        user_limit=1,
        lease_ttl_seconds=1,
    )

    assert result == query_runs.QUERY_CAPACITY_OK
    assert await redis.zscore(query_runs.query_capacity_user_key("u1"), "r1") is None


@pytest.mark.asyncio
async def test_create_run_is_atomic_for_duplicate_run_ids():
    redis = FakeRedis()

    created = await query_runs.create_run(
        redis,
        run_id="r1",
        user_id="u1",
        session_id="s1",
        message_id="m1",
    )
    duplicate = await query_runs.create_run(
        redis,
        run_id="r1",
        user_id="u1",
        session_id="s1",
        message_id="m2",
    )

    run = await query_runs.get_run(redis, "r1")
    assert created is not None
    assert duplicate is None
    assert run["message_id"] == "m1"


@pytest.mark.asyncio
async def test_query_stream_over_capacity_returns_error_without_persisting(monkeypatch):
    from api import query as query_api
    import db.crud.messages as messages_crud
    import db.crud.query_results as query_results_crud
    import db.crud.sessions as sessions_crud

    redis = FakeRedis()
    await query_runs.acquire_query_capacity(
        redis,
        "existing",
        "u2",
        global_limit=1,
        user_limit=0,
        lease_ttl_seconds=120,
    )
    settings = SimpleNamespace(
        max_history_turns=5,
        log_enabled=False,
        query_max_concurrent_global=1,
        query_max_concurrent_per_user=0,
        query_capacity_lease_ttl_seconds=120,
    )
    persisted = []

    async def fake_get_user_allowed_tables(_user_id, _redis, _db):
        return ["table_a"]

    async def fake_get_session(_db, _session_id):
        return SimpleNamespace(user_id="u1")

    def fail_persist(*_args, **_kwargs):
        persisted.append(True)
        raise AssertionError("over-capacity requests must not persist messages")

    monkeypatch.setattr(query_api, "get_redis", lambda: redis)
    monkeypatch.setattr(query_api, "get_settings", lambda: settings)
    monkeypatch.setattr(query_runs, "get_settings", lambda: settings)
    monkeypatch.setattr(query_api, "get_user_allowed_tables", fake_get_user_allowed_tables)
    monkeypatch.setattr(sessions_crud, "get_session", fake_get_session)
    monkeypatch.setattr(messages_crud, "get_messages_by_session_sync", lambda *_args: [])
    monkeypatch.setattr(query_results_crud, "list_query_result_summaries_sync", lambda *_args: [])
    monkeypatch.setattr(messages_crud, "save_user_message_sync", fail_persist)
    monkeypatch.setattr(messages_crud, "save_assistant_message_sync", fail_persist)
    monkeypatch.setattr(
        query_api,
        "run_workflow_stream_with_session",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("workflow must not start")),
    )

    response = await query_api.query_stream(
        q="查一下数据",
        session_id="s1",
        run_id="blocked",
        group_id=None,
        user=SimpleNamespace(user_id="u1"),
        db=object(),
    )
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

    payload = json.loads("".join(chunks).split("data: ", 1)[1].strip())
    assert payload["type"] == "error"
    assert payload["code"] == "query_concurrency_limit"
    assert payload["retry_after_seconds"] == 5
    assert await query_runs.get_run(redis, "blocked") is None
    assert persisted == []
    assert "blocked" not in query_api._RUN_CONTROLS
