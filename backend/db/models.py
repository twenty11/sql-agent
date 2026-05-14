"""SQLAlchemy ORM 模型定义

所有业务表的模型，对应 Alembic 迁移脚本 001_initial_schema.py

修复说明：
- user_roles / role_permissions 纯关联表使用 Table 对象而非映射类，
  避免 asyncpg 在 selectinload 时出现 integer = varchar 类型错误。
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Table, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ── 纯关联表（Table 对象，不需要映射类）────────────────────────────
user_roles_table = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions_table = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", String(36), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

role_table_groups_table = Table(
    "role_table_groups",
    Base.metadata,
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", String(36), ForeignKey("table_groups.id", ondelete="CASCADE"), primary_key=True),
)


# ── 业务实体映射类 ────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    roles: Mapped[list["Role"]] = relationship(
        secondary=user_roles_table, back_populates="users", lazy="select"
    )
    sessions: Mapped[list["Session"]] = relationship(back_populates="user", lazy="select")
    quick_questions: Mapped[list["QuickQuestion"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="select"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", lazy="select")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    users: Mapped[list[User]] = relationship(
        secondary=user_roles_table, back_populates="roles", lazy="select"
    )
    permissions: Mapped[list["Permission"]] = relationship(
        secondary=role_permissions_table, back_populates="roles", lazy="select"
    )
    table_groups: Mapped[list["TableGroup"]] = relationship(
        secondary=role_table_groups_table, back_populates="roles", lazy="select"
    )


class TableGroup(Base):
    """表分组：将多张业务表聚合为一个可授权单元，角色通过分组获得可访问表集合。"""
    __tablename__ = "table_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    tables: Mapped[list["TableGroupMember"]] = relationship(
        back_populates="group", cascade="all, delete-orphan", lazy="select"
    )
    roles: Mapped[list["Role"]] = relationship(
        secondary=role_table_groups_table, back_populates="table_groups", lazy="select"
    )


class TableGroupMember(Base):
    """分组-表 关联（以 schema+name 记录，不物理外键到库表，便于业务表增减）"""
    __tablename__ = "table_group_members"

    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("table_groups.id", ondelete="CASCADE"), primary_key=True
    )
    table_schema: Mapped[str] = mapped_column(String(64), primary_key=True)
    table_name: Mapped[str] = mapped_column(String(128), primary_key=True)

    group: Mapped[TableGroup] = relationship(back_populates="tables")


class Permission(Base):
    __tablename__ = "permissions"
    __table_args__ = (
        UniqueConstraint("resource_type", "resource_name", "action", name="uq_permissions"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    resource_type: Mapped[str] = mapped_column(String(20), nullable=False)   # schema / table
    resource_name: Mapped[str] = mapped_column(String(255), nullable=False)  # 表名或 schema 名
    action: Mapped[str] = mapped_column(String(20), nullable=False)          # read / write

    roles: Mapped[list[Role]] = relationship(
        secondary=role_permissions_table, back_populates="permissions", lazy="select"
    )


class Session(Base):
    """对话会话"""
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="新对话")
    auto_titled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    user: Mapped[User] = relationship(back_populates="sessions", lazy="select")


class Message(Base):
    """会话消息（持久化对话历史）"""
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)   # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class QueryResult(Base):
    """会话级查询结果快照，用于后续分析分支引用历史数据。"""
    __tablename__ = "query_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    fused_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    columns: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    referenced_tables: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class QuickQuestion(Base):
    """用户个人快捷问题"""
    __tablename__ = "quick_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    table_group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("table_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    user: Mapped[User] = relationship(back_populates="quick_questions", lazy="select")
    table_group: Mapped[TableGroup] = relationship(lazy="select")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped[User] = relationship(back_populates="refresh_tokens", lazy="select")
