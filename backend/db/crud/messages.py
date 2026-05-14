"""消息 CRUD — 会话历史读写"""

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session as SyncSession

from db.models import Message, Session as ChatSession


def _latest_messages_statement(session_id: str, limit: int):
    return (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )


def _oldest_first(messages: list[Message]) -> list[Message]:
    return list(reversed(messages))


# ── 异步读取（供 API 端点使用）──────────────────────────────────────

async def get_messages_by_session(
    db: AsyncSession, session_id: str, limit: int = 100
) -> list[Message]:
    """按会话 ID 查询消息列表，按时间升序"""
    result = await db.execute(_latest_messages_statement(session_id, limit))
    return _oldest_first(list(result.scalars().all()))


# ── 同步写入（供 SSE generate() 生成器使用）────────────────────────

def _to_json_safe(obj) -> dict | None:
    """将任意对象序列化为 JSON 安全的 dict，非法类型转为字符串"""
    if obj is None:
        return None
    try:
        return json.loads(json.dumps(obj, default=str, ensure_ascii=False))
    except Exception:
        return None


def save_user_message_sync(session_id: str, content: str) -> str:
    """
    同步保存用户消息到数据库，返回消息ID。
    在 SSE 流开始时调用，确保用户输入不会因流中断而丢失。
    """
    from db.connection import get_engine  # 避免循环导入

    engine = get_engine()
    now = datetime.now(timezone.utc)
    msg_id = str(uuid.uuid4())

    with SyncSession(engine) as session:
        session.add(Message(
            id=msg_id,
            session_id=session_id,
            role="user",
            content=content,
            metadata_=None,
            created_at=now,
        ))
        session.execute(
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(updated_at=now)
        )
        session.commit()
    return msg_id


def save_assistant_message_sync(session_id: str, content: str, metadata: dict | None = None) -> str:
    """
    同步保存助手消息到数据库，返回消息ID。
    在 SSE 流结束时调用。
    """
    from db.connection import get_engine  # 避免循环导入

    engine = get_engine()
    now = datetime.now(timezone.utc)
    msg_id = str(uuid.uuid4())
    safe_metadata = _to_json_safe(metadata)

    with SyncSession(engine) as session:
        session.add(Message(
            id=msg_id,
            session_id=session_id,
            role="assistant",
            content=content,
            metadata_=safe_metadata,
            created_at=now,
        ))
        session.execute(
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(updated_at=now)
        )
        session.commit()
    return msg_id


def update_assistant_message_sync(message_id: str, content: str, metadata: dict | None = None) -> None:
    """
    更新已有助手消息的内容和metadata。
    用于SSE流结束后更新assistant消息。
    """
    from db.connection import get_engine  # 避免循环导入

    engine = get_engine()
    safe_metadata = _to_json_safe(metadata)

    with SyncSession(engine) as session:
        now = datetime.now(timezone.utc)
        result = session.execute(
            select(Message).where(Message.id == message_id)
        )
        msg = result.scalar_one_or_none()
        if msg:
            msg.content = content
            msg.metadata_ = safe_metadata
            session.execute(
                update(ChatSession)
                .where(ChatSession.id == msg.session_id)
                .values(updated_at=now)
            )
            session.commit()


def update_assistant_message_partial_sync(
    message_id: str,
    content: str,
    metadata_patch: dict | None = None,
) -> bool:
    """Update a streaming assistant message without moving it to a terminal state."""
    from db.connection import get_engine  # avoid circular import

    engine = get_engine()
    safe_patch = _to_json_safe(metadata_patch) or {}

    with SyncSession(engine) as session:
        now = datetime.now(timezone.utc)
        result = session.execute(select(Message).where(Message.id == message_id))
        msg = result.scalar_one_or_none()
        if not msg or msg.role != "assistant":
            return False

        current_metadata = dict(msg.metadata_ or {})
        current_status = current_metadata.get("status")
        if current_status in {"completed", "failed", "stopped"}:
            return False

        current_metadata.update(safe_patch)
        current_metadata["status"] = "streaming"
        msg.content = content
        msg.metadata_ = current_metadata
        session.execute(
            update(ChatSession)
            .where(ChatSession.id == msg.session_id)
            .values(updated_at=now)
        )
        session.commit()
        return True


def update_assistant_message_if_streaming_sync(
    message_id: str,
    content: str,
    metadata: dict | None = None,
) -> bool:
    """CAS update for terminal assistant states: only streaming may transition."""
    from db.connection import get_engine  # avoid circular import

    engine = get_engine()
    safe_metadata = _to_json_safe(metadata) or {}

    with SyncSession(engine) as session:
        now = datetime.now(timezone.utc)
        result = session.execute(select(Message).where(Message.id == message_id))
        msg = result.scalar_one_or_none()
        if not msg or msg.role != "assistant":
            return False

        current_metadata = dict(msg.metadata_ or {})
        current_status = current_metadata.get("status")
        if current_status in {"completed", "failed", "stopped"}:
            return False

        current_metadata.update(safe_metadata)
        msg.content = content
        msg.metadata_ = current_metadata
        session.execute(
            update(ChatSession)
            .where(ChatSession.id == msg.session_id)
            .values(updated_at=now)
        )
        session.commit()
        return True


def save_messages_sync(
    session_id: str,
    user_content: str,
    assistant_content: str,
    metadata: dict | None = None,
) -> tuple[str, str]:
    """
    同步写入一对消息（用户提问 + AI 回答）到数据库。
    在 SSE 流式生成器结束后调用，使用同步 SQLAlchemy Session。
    返回 (user_msg_id, assistant_msg_id)
    """
    from db.connection import get_engine  # 避免循环导入

    engine = get_engine()
    now = datetime.now(timezone.utc)
    user_msg_id = str(uuid.uuid4())
    assistant_msg_id = str(uuid.uuid4())
    safe_metadata = _to_json_safe(metadata)

    with SyncSession(engine) as session:
        session.add(Message(
            id=user_msg_id,
            session_id=session_id,
            role="user",
            content=user_content,
            metadata_=None,
            created_at=now,
        ))
        session.add(Message(
            id=assistant_msg_id,
            session_id=session_id,
            role="assistant",
            content=assistant_content,
            metadata_=safe_metadata,
            created_at=now,
        ))
        session.execute(
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(updated_at=now)
        )
        session.commit()
    return user_msg_id, assistant_msg_id


def get_messages_by_session_sync(
    session_id: str,
    limit: int = 100,
) -> list[Message]:
    """
    同步版本的消息查询，供 SSE generate() 生成器使用。
    按会话 ID 查询消息列表，按时间升序返回。
    """
    from db.connection import get_engine  # 避免循环导入

    engine = get_engine()
    with SyncSession(engine) as session:
        result = session.execute(_latest_messages_statement(session_id, limit))
        return _oldest_first(list(result.scalars().all()))
