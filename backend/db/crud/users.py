"""用户 CRUD 操作"""

from typing import Optional
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import User


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(
        select(User).where(User.email == email).options(selectinload(User.roles))
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    result = await db.execute(
        select(User).where(User.id == user_id).options(selectinload(User.roles))
    )
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    email: str,
    hashed_password: str,
    full_name: Optional[str] = None,
) -> User:
    user = User(email=email, hashed_password=hashed_password, full_name=full_name)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user(
    db: AsyncSession,
    user_id: str,
    full_name: Optional[str] = None,
    hashed_password: Optional[str] = None,
) -> Optional[User]:
    user = await get_user_by_id(db, user_id)
    if not user:
        return None
    if full_name is not None:
        user.full_name = full_name
    if hashed_password is not None:
        user.hashed_password = hashed_password
    await db.commit()
    await db.refresh(user)
    return user


async def set_user_active(db: AsyncSession, user_id: str, is_active: bool) -> Optional[User]:
    user = await get_user_by_id(db, user_id)
    if not user:
        return None
    user.is_active = is_active
    await db.commit()
    await db.refresh(user)
    return user


async def list_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[User]:
    result = await db.execute(
        select(User).options(selectinload(User.roles)).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


async def delete_user(db: AsyncSession, user_id: str) -> bool:
    result = await db.execute(select(User.id).where(User.id == user_id))
    if result.scalar_one_or_none() is None:
        return False
    # Use Core DELETE so PostgreSQL ON DELETE rules handle dependent rows.
    # ORM instance deletion tries to NULL child FKs such as refresh_tokens.user_id.
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()
    return True
