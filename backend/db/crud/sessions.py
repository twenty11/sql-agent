"""对话会话 CRUD 操作"""

from typing import Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Session


async def create_session(db: AsyncSession, user_id: str, title: str = "新对话") -> Session:
    session = Session(user_id=user_id, title=title)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(db: AsyncSession, session_id: str) -> Optional[Session]:
    result = await db.execute(select(Session).where(Session.id == session_id))
    return result.scalar_one_or_none()


async def get_sessions_for_user(
    db: AsyncSession, user_id: str, skip: int = 0, limit: int = 50
) -> list[Session]:
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user_id, Session.is_active == True)
        .order_by(desc(Session.updated_at))
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_session_title(
    db: AsyncSession, session_id: str, title: str, mark_user_renamed: bool = False
) -> Optional[Session]:
    session = await get_session(db, session_id)
    if not session:
        return None
    session.title = title
    if mark_user_renamed:
        session.auto_titled = False
    await db.commit()
    await db.refresh(session)
    return session


async def delete_session(db: AsyncSession, session_id: str) -> bool:
    session = await get_session(db, session_id)
    if not session:
        return False
    await db.delete(session)
    await db.commit()
    return True
