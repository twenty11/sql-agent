"""
FastAPI 后端入口 — 企业级版本

路由说明:
- /auth/*         认证（登录/刷新/登出）
- /api/query      SSE 流式查询（需登录）
- /api/sessions/* 会话管理（需登录）
- /profile/*      当前用户设置和可访问资源（需登录）
- /admin/*        管理员后台（需 admin 角色）
- /health         健康检查
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from dotenv import load_dotenv

from config import get_settings
from vectorstore.milvus_store import get_milvus_store
from graph.workflow import create_workflow_without_answer, save_graph_png

# 路由模块
from api.auth import router as auth_router
from api.query import router as query_router
from api.sessions import router as sessions_router
from api.quick_questions import router as quick_questions_router
from api.profile import router as profile_router
from api.admin.users import router as admin_users_router
from api.admin.audit import router as admin_audit_router
from api.admin.vectorstore import router as admin_vs_router
from api.admin.roles import router as admin_roles_router
from api.admin.tables import router as admin_tables_router
from api.admin.table_groups import router as admin_table_groups_router

# 加载环境变量
load_dotenv()

# LangSmith 追踪
os.environ["LANGSMITH_TRACING"] = os.getenv("LANGSMITH_TRACING", "false")
os.environ["LANGSMITH_API_KEY"] = os.getenv("LANGSMITH_API_KEY", "")
os.environ["LANGSMITH_PROJECT"] = os.getenv("LANGSMITH_PROJECT", "sql-agent")
os.environ["LANGSMITH_ENDPOINT"] = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.auto_sync_on_startup:
        print("[Milvus] 确认 collection 就绪...")
        try:
            get_milvus_store()
            print("[Milvus] Collection 已就绪")
        except Exception as e:
            print(f"[Milvus] 启动时连接失败（可稍后重建）: {e}")
    try:
        yield
    finally:
        # 应用退出时释放 Redis / 异步数据库连接池
        try:
            from auth.dependencies import close_redis
            await close_redis()
        except Exception as e:
            print(f"[lifespan] 关闭 Redis 失败: {e}")
        try:
            from db.async_connection import get_async_engine
            await get_async_engine().dispose()
        except Exception as e:
            print(f"[lifespan] 释放异步数据库引擎失败: {e}")


app = FastAPI(title="DataLens API — 企业版", version="2.0.0", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router)
app.include_router(query_router)
app.include_router(sessions_router)
app.include_router(quick_questions_router)
app.include_router(profile_router)
app.include_router(admin_users_router)
app.include_router(admin_audit_router)
app.include_router(admin_vs_router)
app.include_router(admin_roles_router)
app.include_router(admin_tables_router)
app.include_router(admin_table_groups_router)


@app.get("/health")
async def health():
    """健康检查：返回数据库和 Redis 连接状态"""
    status = {"status": "ok", "postgres": False, "redis": False}
    try:
        from db.connection import test_connection
        status["postgres"] = test_connection()
    except Exception:
        pass
    try:
        from auth.dependencies import get_redis
        redis = get_redis()
        await redis.ping()
        status["redis"] = True
    except Exception:
        pass
    return status


@app.get("/api/workflow/graph")
async def workflow_graph():
    wf = create_workflow_without_answer()
    compiled = wf.compile()
    save_graph_png(compiled)
    return FileResponse("graph_.png")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8080,
        workers=1,
        timeout_keep_alive=120,
        limit_concurrency=10,
        limit_max_requests=1000,
    )
