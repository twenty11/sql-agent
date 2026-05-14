"""向量库服务（Milvus 版）"""

from typing import Dict


class VectorStoreService:
    """向量库服务：封装 Milvus 状态查询和同步触发。"""

    @staticmethod
    def sync() -> Dict:
        """消费 pending/pending_retry 行，同步到 Milvus。"""
        try:
            from services.milvus_sync import flush_pending_syncs
            report = flush_pending_syncs()
            return {
                "success": True,
                "message": "向量库同步完成",
                "data": {"synced": report.success, "failed": report.failed},
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_status() -> Dict:
        """返回 Milvus collection 统计。"""
        try:
            from vectorstore.milvus_store import get_milvus_store
            store = get_milvus_store()
            tc = store.count_tables()
            return {
                "success": True,
                "data": {
                    "table_count": tc,
                    "status": "ready" if tc > 0 else "empty",
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
