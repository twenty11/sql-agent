"""
Milvus 向量数据库管理模块

collection:
  table_schemas  — 表级检索（text2sql 主路径）
"""

import hashlib
import threading
from typing import List, Optional

from pymilvus import (
    Collection, CollectionSchema, DataType, FieldSchema,
    connections, utility,
)

from config import get_settings
from .embeddings import get_embeddings

EMBEDDING_DIM = 512  # bge-small-zh-v1.5

TABLE_COLLECTION = "table_schemas"

# HNSW index + COSINE metric (bge-m3 已 L2 normalize，COSINE 安全)
_HNSW_INDEX = {
    "metric_type": "COSINE",
    "index_type": "HNSW",
    "params": {"M": 16, "efConstruction": 200},
}
_SEARCH_PARAMS = {"metric_type": "COSINE", "params": {"ef": 64}}


def _table_schema() -> CollectionSchema:
    fields = [
        FieldSchema("pk", DataType.VARCHAR, max_length=36, is_primary=True, auto_id=False),
        FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
        FieldSchema("physical_schema", DataType.VARCHAR, max_length=64),
        FieldSchema("physical_name", DataType.VARCHAR, max_length=128),
        FieldSchema("display_name", DataType.VARCHAR, max_length=255),
        FieldSchema("table_comment", DataType.VARCHAR, max_length=2048),
        FieldSchema("column_count", DataType.INT32),
        FieldSchema("status", DataType.VARCHAR, max_length=16),
        FieldSchema("doc_text", DataType.VARCHAR, max_length=65535),
    ]
    return CollectionSchema(fields, description="table-level schema for text2sql retrieval")



class MilvusStore:
    """
    Milvus 向量库管理器。

    保留与原 VectorStoreManager 相同的外部接口（search_schemas / get_table_count），
    同时增加细粒度的 upsert/delete 方法供 admin pipeline 调用。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connected = False
        self._table_col: Optional[Collection] = None

    # ── 连接 ────────────────────────────────────────────────────

    def connect(self) -> None:
        if self._connected:
            return
        s = get_settings()
        connections.connect(
            alias=s.milvus_alias,
            host=s.milvus_host,
            port=s.milvus_port,
            user=s.milvus_user,
            password=s.milvus_password,
        )
        self._connected = True

    def ensure_collections(self) -> None:
        """幂等地创建 collection 和索引（若不存在则创建）。"""
        self.connect()
        self._table_col = self._ensure_one(TABLE_COLLECTION, _table_schema())

    def _ensure_one(self, name: str, schema: CollectionSchema) -> Collection:
        alias = get_settings().milvus_alias
        if utility.has_collection(name, using=alias):
            col = Collection(name, using=alias)
            existing_fields = {f.name for f in col.schema.fields}
            expected_fields = {f.name for f in schema.fields}
            if not expected_fields.issubset(existing_fields):
                # schema 缺字段（如新增 display_name），drop 后重建
                col.release()
                utility.drop_collection(name, using=alias)
                col = Collection(name, schema=schema, using=alias)
                col.create_index("embedding", _HNSW_INDEX)
        else:
            col = Collection(name, schema=schema, using=alias)
            col.create_index("embedding", _HNSW_INDEX)
        col.load()
        return col

    def _tables(self) -> Collection:
        s = get_settings()
        if self._table_col is None or not utility.has_collection(TABLE_COLLECTION, using=s.milvus_alias):
            self.ensure_collections()
        return self._table_col  # type: ignore[return-value]

    # ── 表级 upsert / delete ─────────────────────────────────────

    def upsert_table(
        self,
        table_id: str,
        doc_text: str,
        physical_schema: str,
        physical_name: str,
        display_name: str,
        table_comment: str,
        column_count: int,
        status: str = "active",
    ) -> None:
        emb = get_embeddings().embed_documents([doc_text])[0]
        col = self._tables()
        entity = {
            "pk": table_id,
            "embedding": emb,
            "physical_schema": physical_schema[:64],
            "physical_name": physical_name[:128],
            "display_name": (display_name or "")[:255],
            "table_comment": (table_comment or "")[:2048],
            "column_count": column_count,
            "status": status[:16],
            "doc_text": doc_text[:65535],
        }
        upsert = getattr(col, "upsert", None)
        if callable(upsert):
            try:
                upsert([entity])
            except Exception:
                col.delete(f'pk in ["{table_id}"]')
                col.flush()
                col.insert([entity])
        else:
            col.delete(f'pk in ["{table_id}"]')
            col.flush()
            col.insert([entity])
        col.flush()

    def delete_table(self, table_id: str) -> None:
        self._tables().delete(f'pk in ["{table_id}"]')
        self._tables().flush()

    # ── 检索 ─────────────────────────────────────────────────────

    def search_tables(
        self, query: str, top_k: Optional[int] = None,
        table_names_filter: Optional[List[str]] = None,
    ) -> List[str]:
        """返回 doc_text 列表（与旧 search_schemas 接口兼容）。

        Args:
            table_names_filter: 若提供，则只在这些 physical_name 中检索（分组过滤）。
        """
        if top_k is None:
            top_k = get_settings().retrieval_top_k
        emb = get_embeddings().embed_query(query)
        col = self._tables()

        expr = 'status == "active"'
        if table_names_filter:
            names_str = ", ".join(f'"{n}"' for n in table_names_filter)
            expr = f'status == "active" && physical_name in [{names_str}]'

        results = col.search(
            data=[emb],
            anns_field="embedding",
            param=_SEARCH_PARAMS,
            limit=top_k,
            expr=expr,
            output_fields=["doc_text"],
        )
        return [hit.entity.get("doc_text", "") for hit in results[0]]

    # ── 统计 / 状态 ──────────────────────────────────────────────

    def count_tables(self) -> int:
        try:
            rows = self._tables().query(
                expr='status == "active"',
                output_fields=["pk"],
                limit=16384,
            )
            return len({str(row.get("pk")) for row in rows if row.get("pk")})
        except Exception:
            try:
                return self._tables().num_entities
            except Exception:
                return 0

    def ping(self) -> bool:
        """测试 Milvus 连接是否正常（与是否有数据无关）。"""
        try:
            self.connect()
            utility.list_collections(using=get_settings().milvus_alias)
            return True
        except Exception:
            return False

    # ── 向后兼容接口（nodes.py / admin 继续可用）────────────────

    def search_schemas(
        self, query: str, top_k: Optional[int] = None,
        table_names_filter: Optional[List[str]] = None,
    ) -> List[str]:
        """向后兼容：等价于 search_tables。"""
        return self.search_tables(query, top_k, table_names_filter)

    def get_table_count(self) -> int:
        """向后兼容：等价于 count_tables。"""
        return self.count_tables()


# ── 全局单例 ─────────────────────────────────────────────────────

_milvus_store: Optional[MilvusStore] = None
_milvus_lock = threading.Lock()


def get_milvus_store() -> MilvusStore:
    """线程安全的单例工厂，供 nodes.py 和其他模块使用。"""
    global _milvus_store
    if _milvus_store is None:
        with _milvus_lock:
            if _milvus_store is None:
                store = MilvusStore()
                store.ensure_collections()
                _milvus_store = store
    return _milvus_store


def payload_hash(doc_text: str) -> str:
    """计算 doc_text 的 sha256，用于 vector_sync_log.payload_hash 幂等检查。"""
    return hashlib.sha256(doc_text.encode()).hexdigest()
