import importlib
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _load_audit_task(monkeypatch):
    monkeypatch.setenv("PG_DATABASE", "test")
    monkeypatch.setenv("PG_PASSWORD", "test")
    monkeypatch.setenv("LLM_MODEL_NAME", "test")
    monkeypatch.setenv("EMBEDDING_MODEL_PATH", "test")

    import config

    config.get_settings.cache_clear()
    return importlib.import_module("tasks.audit")


class FakeSession:
    def __init__(self, calls):
        self.calls = calls

    async def __aenter__(self):
        self.calls.append("enter")
        return "db-session"

    async def __aexit__(self, exc_type, exc, tb):
        self.calls.append(("exit", exc_type.__name__ if exc_type else None))


class FakeEngine:
    def __init__(self, calls):
        self.calls = calls

    async def dispose(self):
        self.calls.append("dispose")


@pytest.mark.asyncio
async def test_write_log_disposes_async_engine_after_success(monkeypatch):
    audit_task = _load_audit_task(monkeypatch)
    async_connection = importlib.import_module("db.async_connection")
    audit_crud = importlib.import_module("db.crud.audit")
    calls = []

    async def fake_write_audit_log(db, **kwargs):
        calls.append(("write", db, kwargs["user_id"]))

    monkeypatch.setattr(async_connection, "AsyncSessionLocal", lambda: FakeSession(calls))
    monkeypatch.setattr(async_connection, "get_async_engine", lambda: FakeEngine(calls))
    monkeypatch.setattr(audit_crud, "write_audit_log", fake_write_audit_log)

    await audit_task._write_log("u1", "s1", "q", "sql", True, 12, 3, None)

    assert calls == [
        "enter",
        ("write", "db-session", "u1"),
        ("exit", None),
        "dispose",
    ]


@pytest.mark.asyncio
async def test_write_log_disposes_async_engine_after_error(monkeypatch):
    audit_task = _load_audit_task(monkeypatch)
    async_connection = importlib.import_module("db.async_connection")
    audit_crud = importlib.import_module("db.crud.audit")
    calls = []

    async def fake_write_audit_log(db, **kwargs):
        calls.append("write")
        raise RuntimeError("boom")

    monkeypatch.setattr(async_connection, "AsyncSessionLocal", lambda: FakeSession(calls))
    monkeypatch.setattr(async_connection, "get_async_engine", lambda: FakeEngine(calls))
    monkeypatch.setattr(audit_crud, "write_audit_log", fake_write_audit_log)

    with pytest.raises(RuntimeError, match="boom"):
        await audit_task._write_log("u1", "s1", "q", "sql", True, 12, 3, None)

    assert calls == [
        "enter",
        "write",
        ("exit", "RuntimeError"),
        "dispose",
    ]
