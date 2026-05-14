import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.crud.users import delete_user


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeSession:
    def __init__(self, existing_user_id=None):
        self.existing_user_id = existing_user_id
        self.statements = []
        self.committed = False

    async def execute(self, statement):
        self.statements.append(statement)
        if len(self.statements) == 1:
            return _ScalarResult(self.existing_user_id)
        return _ScalarResult(None)

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_delete_user_uses_core_delete_to_allow_fk_cascade():
    db = _FakeSession(existing_user_id="u1")

    assert await delete_user(db, "u1") is True

    assert len(db.statements) == 2
    assert db.statements[0].__visit_name__ == "select"
    assert db.statements[1].__visit_name__ == "delete"
    assert db.committed is True


@pytest.mark.asyncio
async def test_delete_user_returns_false_when_missing():
    db = _FakeSession(existing_user_id=None)

    assert await delete_user(db, "missing") is False

    assert len(db.statements) == 1
    assert db.committed is False
