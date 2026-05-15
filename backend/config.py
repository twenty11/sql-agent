"""
配置管理模块
使用 pydantic-settings 从环境变量和 .env 文件加载配置
"""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置类"""

    # PostgreSQL 数据库配置
    pg_host: str = Field(default="localhost", description="PostgreSQL 主机地址")
    pg_port: int = Field(default=5432, description="PostgreSQL 端口")
    pg_database: str = Field(description="数据库名称")
    pg_user: str = Field(default="postgres", description="数据库用户名")
    pg_password: str = Field(description="数据库密码")
    pg_schema: str = Field(default="sql_agent", description="业务数据 Schema")
    pg_public_schema: str = Field(default="public", description="公共表 Schema（用户、权限等）")

    # LLM 配置 (兼容 OpenAI 接口)
    llm_base_url: str = Field(
        default="http://localhost:8000/v1",
        description="LLM API 基础 URL (vLLM/Ollama)"
    )
    llm_model_name: str = Field(description="LLM 模型名称")
    llm_api_key: str = Field(default="not-needed", description="API Key (本地模型可忽略)")

    # 嵌入模型配置
    embedding_model_path: str = Field(description="本地嵌入模型路径 (如 bge-m3)")

    # Milvus 向量数据库配置
    milvus_host: str = Field(default="localhost", description="Milvus 主机地址")
    milvus_port: str = Field(default="19530", description="Milvus 端口")
    milvus_user: str = Field(default="root", description="Milvus 用户名")
    milvus_password: str = Field(default="", description="Milvus 密码")
    milvus_alias: str = Field(default="default", description="Milvus 连接别名")

    # 上传文件暂存目录
    upload_staging_dir: str = Field(
        default="./upload_staging",
        description="Admin 上传文件的暂存目录"
    )

    # 工作流配置
    retrieval_top_k: int = Field(default=5, description="检索返回的 Top-K 表数量")
    max_retry_count: int = Field(default=3, description="SQL 生成/执行最大重试次数")
    query_preview_max_rows: int = Field(default=1000, description="问答链路最多返回的预览行数")
    query_statement_timeout_ms: int = Field(default=60000, description="问答查询 SQL 超时时间（毫秒）")
    export_statement_timeout_ms: int = Field(default=300000, description="导出 SQL 超时时间（毫秒）")
    export_chunk_size: int = Field(default=2000, description="导出分批读取行数")
    export_max_rows: int = Field(default=1048575, description="单次 Excel 导出最大数据行数")

    # 启动配置
    auto_sync_on_startup: bool = Field(
        default=False,
        description="启动时是否自动同步向量库"
    )

    # 日志配置
    log_enabled: bool = Field(
        default=True,
        description="是否启用日志系统"
    )
    log_dir: str = Field(
        default="./logs",
        description="日志目录路径"
    )
    log_max_bytes: int = Field(
        default=5242880,  # 5MB
        description="单个日志文件最大字节数"
    )
    log_backup_count: int = Field(
        default=5,
        description="日志备份文件数量"
    )
    log_format: str = Field(
        default="json",
        description="日志格式 (json 或 readable)"
    )

    # Redis 配置
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis 连接 URL"
    )

    # JWT 认证配置
    jwt_secret_key: str = Field(
        default="change-this-secret-in-production",
        description="JWT 签名密钥"
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT 算法")
    access_token_expire_minutes: int = Field(default=30, description="Access Token 有效期（分钟）")
    refresh_token_expire_days: int = Field(default=7, description="Refresh Token 有效期（天）")

    # Celery 异步任务配置
    celery_broker_url: str = Field(
        default="redis://localhost:6379/1",
        description="Celery Broker URL"
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/2",
        description="Celery Result Backend URL"
    )

    # 多轮对话配置
    max_history_turns: int = Field(default=5, description="最大携带历史轮数")
    session_ttl_seconds: int = Field(default=3600, description="会话 Redis 缓存 TTL（秒）")

    @property
    def pg_connection_string(self) -> str:
        """构建 PostgreSQL 连接字符串

        search_path 包含公共 schema（用户、权限等）和业务 schema（数据表）
        """
        return (
            f"postgresql://{self.pg_user}:{self.pg_password}"
            f"@{self.pg_host}:{self.pg_port}/{self.pg_database}"
            f"?options=-c%20search_path%3D{self.pg_public_schema},meta,{self.pg_schema}"
        )

    class Config:
        env_file = str(Path(__file__).parent / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """
    获取配置单例
    使用 lru_cache 确保配置只加载一次
    """
    return Settings()
