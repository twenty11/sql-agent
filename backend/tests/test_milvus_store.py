import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vectorstore import milvus_store
from vectorstore.milvus_store import EMBEDDING_DIM, MilvusStore


class _FakeEmbeddings:
    def embed_documents(self, texts):
        return [[0.1] * EMBEDDING_DIM for _ in texts]


class _UpsertCollection:
    def __init__(self):
        self.upserted = []
        self.deleted = []
        self.inserted = []
        self.flush_count = 0

    def upsert(self, rows):
        self.upserted.extend(rows)

    def delete(self, expr):
        self.deleted.append(expr)

    def insert(self, rows):
        self.inserted.extend(rows)

    def flush(self):
        self.flush_count += 1


class _FallbackCollection(_UpsertCollection):
    def upsert(self, rows):
        raise RuntimeError("upsert unavailable")


def _store_with_collection(monkeypatch, collection):
    store = MilvusStore()
    monkeypatch.setattr(milvus_store, "get_embeddings", lambda: _FakeEmbeddings())
    monkeypatch.setattr(store, "_tables", lambda: collection)
    return store


def test_upsert_table_uses_milvus_upsert_when_available(monkeypatch):
    collection = _UpsertCollection()
    store = _store_with_collection(monkeypatch, collection)

    store.upsert_table(
        table_id="table-1",
        doc_text="doc",
        physical_schema="sql_agent",
        physical_name="target_table",
        display_name="目标表",
        table_comment="comment",
        column_count=3,
    )

    assert [row["pk"] for row in collection.upserted] == ["table-1"]
    assert collection.deleted == []
    assert collection.inserted == []
    assert collection.flush_count == 1


def test_upsert_table_falls_back_to_delete_insert(monkeypatch):
    collection = _FallbackCollection()
    store = _store_with_collection(monkeypatch, collection)

    store.upsert_table(
        table_id="table-1",
        doc_text="doc",
        physical_schema="sql_agent",
        physical_name="target_table",
        display_name="目标表",
        table_comment="comment",
        column_count=3,
    )

    assert collection.deleted == ['pk in ["table-1"]']
    assert [row["pk"] for row in collection.inserted] == ["table-1"]
    assert collection.flush_count == 2


class _CountingCollection:
    num_entities = 99

    def __init__(self, rows):
        self.rows = rows

    def query(self, **kwargs):
        return self.rows


def test_count_tables_uses_distinct_active_primary_keys(monkeypatch):
    store = MilvusStore()
    collection = _CountingCollection([
        {"pk": "table-1"},
        {"pk": "table-1"},
        {"pk": "table-2"},
    ])
    monkeypatch.setattr(store, "_tables", lambda: collection)

    assert store.count_tables() == 2
