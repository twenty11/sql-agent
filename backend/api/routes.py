"""
API 路由模块
定义管理页面相关的 API 端点
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List, Optional

from services.vectorstore_service import VectorStoreService
from graph.workflow import run_sql_evaluation_with_retry

router = APIRouter(prefix="/api", tags=["API"])


class SyncRequest(BaseModel):
    pass


@router.post("/vectorstore/sync")
async def sync_vectorstore(request: SyncRequest):
    return VectorStoreService.sync()


@router.get("/vectorstore/status")
async def get_vectorstore_status():
    return VectorStoreService.get_status()


class SQLEvaluationRequest(BaseModel):
    question: str


class SQLEvaluationResponse(BaseModel):
    question: str
    generated_sql: str
    selected_tables: List[dict]
    join_plan: Optional[dict] = None
    retrieved_schemas: List
    table_selection_reason: str
    sql_valid: bool = False
    sql_check_message: str = ""
    error: Optional[str] = None


@router.post("/sql/evaluate")
async def evaluate_sql_generation(request: SQLEvaluationRequest):
    result = run_sql_evaluation_with_retry(request.question)
    return SQLEvaluationResponse(**result)