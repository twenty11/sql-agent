import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api import query as query_api
from db.crud.query_results import get_query_result_for_user
from graph.nodes import _fetch_preview_rows


class FakePreviewResult:
    def __init__(self, rows):
        self.rows = rows
        self.fetchmany_size = None
        self.fetchall_called = False

    def fetchmany(self, size):
        self.fetchmany_size = size
        return self.rows

    def fetchall(self):
        self.fetchall_called = True
        raise AssertionError("preview queries must not call fetchall")


def test_fetch_preview_rows_fetches_limit_plus_one_without_fetchall():
    result = FakePreviewResult([("r1",), ("r2",), ("r3",)])

    rows, truncated = _fetch_preview_rows(result, 2)

    assert rows == [("r1",), ("r2",)]
    assert truncated is True
    assert result.fetchmany_size == 3
    assert result.fetchall_called is False


def test_validate_export_sql_rejects_tables_outside_current_permissions():
    with pytest.raises(HTTPException) as exc:
        query_api._validate_export_sql("SELECT * FROM table_a", ["table_b"])

    assert exc.value.status_code == 403
    assert "权限不足" in exc.value.detail


class FakeScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeAsyncSession:
    def __init__(self):
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return FakeScalarResult("result")


@pytest.mark.asyncio
async def test_get_query_result_for_user_scopes_result_to_session_owner():
    db = FakeAsyncSession()

    result = await get_query_result_for_user(db, "qr1", "u1")

    compiled = str(db.statement)
    assert result == "result"
    assert "JOIN sessions ON sessions.id = query_results.session_id" in compiled
    assert "sessions.user_id" in compiled


class FakeExportResult:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    def keys(self):
        return ["id"]

    def fetchmany(self, _size):
        if not self.chunks:
            return []
        return self.chunks.pop(0)


class FakeExportConnection:
    def __init__(self, result):
        self.result = result

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, _params=None):
        sql = str(statement)
        if "set_config" in sql:
            return None
        return self.result

    def execution_options(self, **_kwargs):
        return self


class FakeExportEngine:
    def __init__(self, result):
        self.result = result

    def connect(self):
        return FakeExportConnection(self.result)


def test_write_sql_export_xlsx_rejects_results_over_export_cap(monkeypatch):
    settings = SimpleNamespace(
        export_chunk_size=2,
        export_max_rows=2,
        export_statement_timeout_ms=300000,
    )
    result = FakeExportResult([[(1,), (2,)], [(3,)]])

    monkeypatch.setattr(query_api, "get_settings", lambda: settings)
    monkeypatch.setattr("db.connection.get_engine", lambda: FakeExportEngine(result))

    with pytest.raises(query_api.ExportTooLargeError):
        query_api._write_sql_export_xlsx_sync("SELECT * FROM table_a", "r1")
