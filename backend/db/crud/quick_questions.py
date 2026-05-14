"""个人快捷问题 CRUD"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import QuickQuestion


async def list_quick_questions(db: AsyncSession, user_id: str) -> list[QuickQuestion]:
    result = await db.execute(
        select(QuickQuestion)
        .where(QuickQuestion.user_id == user_id)
        .order_by(
            desc(QuickQuestion.is_pinned),
            QuickQuestion.sort_order.asc(),
            desc(QuickQuestion.updated_at),
        )
    )
    return list(result.scalars().all())


async def get_quick_question(
    db: AsyncSession, question_id: str, user_id: str
) -> Optional[QuickQuestion]:
    result = await db.execute(
        select(QuickQuestion).where(
            QuickQuestion.id == question_id,
            QuickQuestion.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def create_quick_question(
    db: AsyncSession,
    user_id: str,
    question_text: str,
    display_name: str | None = None,
    table_group_id: str = "",
    is_pinned: bool = True,
) -> QuickQuestion:
    max_order = await db.scalar(
        select(func.max(QuickQuestion.sort_order)).where(QuickQuestion.user_id == user_id)
    )
    item = QuickQuestion(
        user_id=user_id,
        display_name=display_name,
        question_text=question_text,
        table_group_id=table_group_id,
        is_pinned=is_pinned,
        sort_order=(max_order or 0) + 10,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def update_quick_question(
    db: AsyncSession,
    item: QuickQuestion,
    *,
    display_name: str | None | object = ...,
    question_text: str | None = None,
    table_group_id: str | object = ...,
    is_pinned: bool | None = None,
) -> QuickQuestion:
    if display_name is not ...:
        item.display_name = display_name
    if question_text is not None:
        item.question_text = question_text
    if table_group_id is not ...:
        item.table_group_id = table_group_id
    if is_pinned is not None:
        item.is_pinned = is_pinned
    await db.commit()
    await db.refresh(item)
    return item


async def delete_quick_question(db: AsyncSession, item: QuickQuestion) -> None:
    await db.delete(item)
    await db.commit()


async def reorder_quick_questions(
    db: AsyncSession, user_id: str, ordered_ids: list[str]
) -> list[QuickQuestion]:
    if not ordered_ids:
        return await list_quick_questions(db, user_id)

    result = await db.execute(
        select(QuickQuestion).where(
            QuickQuestion.user_id == user_id,
            QuickQuestion.id.in_(ordered_ids),
        )
    )
    by_id = {item.id: item for item in result.scalars().all()}
    for index, item_id in enumerate(ordered_ids):
        item = by_id.get(item_id)
        if item:
            item.sort_order = (index + 1) * 10

    await db.commit()
    return await list_quick_questions(db, user_id)


async def mark_quick_question_used(
    db: AsyncSession, item: QuickQuestion
) -> QuickQuestion:
    item.usage_count += 1
    item.last_used_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(item)
    return item
