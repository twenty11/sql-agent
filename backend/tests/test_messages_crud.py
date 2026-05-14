import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.crud.messages import get_messages_by_session, _latest_messages_statement


class _ScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _Result:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return _ScalarResult(self._values)


class _FakeAsyncSession:
    def __init__(self, values):
        self.values = values
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return _Result(self.values)


@dataclass
class _Message:
    id: str
    created_at: datetime


@pytest.mark.asyncio
async def test_get_messages_by_session_fetches_latest_limit_and_returns_ascending():
    now = datetime.now(timezone.utc)
    newest = _Message("newest", now)
    older = _Message("older", now - timedelta(seconds=1))
    db = _FakeAsyncSession([newest, older])

    messages = await get_messages_by_session(db, "s1", limit=2)

    assert messages == [older, newest]
    compiled = str(db.statement.compile(compile_kwargs={"literal_binds": True}))
    assert "ORDER BY messages.created_at DESC" in compiled
    assert "LIMIT 2" in compiled


def test_latest_messages_statement_is_shared_by_async_and_sync_readers():
    compiled = str(_latest_messages_statement("s1", 25).compile(compile_kwargs={"literal_binds": True}))

    assert "WHERE messages.session_id = 's1'" in compiled
    assert "ORDER BY messages.created_at DESC" in compiled
    assert "LIMIT 25" in compiled
