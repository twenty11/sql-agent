import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db.connection as connection


class FakeEngine:
    def __init__(self):
        self.disposed = False

    def dispose(self):
        self.disposed = True


def test_get_engine_reuses_single_process_engine(monkeypatch):
    created = []

    def fake_create_engine(*_args, **_kwargs):
        engine = FakeEngine()
        created.append(engine)
        return engine

    monkeypatch.setattr(connection, "_engine", None)
    monkeypatch.setattr(
        connection,
        "get_settings",
        lambda: SimpleNamespace(pg_connection_string="postgresql://user:pass@db/app"),
    )
    monkeypatch.setattr(connection, "create_engine", fake_create_engine)

    first = connection.get_engine()
    second = connection.get_engine()

    assert first is second
    assert created == [first]


def test_dispose_engine_disposes_existing_engine_and_allows_recreate(monkeypatch):
    created = []

    def fake_create_engine(*_args, **_kwargs):
        engine = FakeEngine()
        created.append(engine)
        return engine

    monkeypatch.setattr(connection, "_engine", None)
    monkeypatch.setattr(
        connection,
        "get_settings",
        lambda: SimpleNamespace(pg_connection_string="postgresql://user:pass@db/app"),
    )
    monkeypatch.setattr(connection, "create_engine", fake_create_engine)

    first = connection.get_engine()
    connection.dispose_engine()
    second = connection.get_engine()

    assert first.disposed is True
    assert second is not first
    assert created == [first, second]


def test_dispose_engine_does_not_create_engine(monkeypatch):
    def fail_create_engine(*_args, **_kwargs):
        raise AssertionError("dispose_engine must not create a new engine")

    monkeypatch.setattr(connection, "_engine", None)
    monkeypatch.setattr(connection, "create_engine", fail_create_engine)

    connection.dispose_engine()
    assert connection._engine is None
