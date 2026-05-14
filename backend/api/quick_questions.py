"""个人快捷问题路由"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_async_session, get_current_user
from auth.dependencies import UserContext
from db.crud.quick_questions import (
    create_quick_question,
    delete_quick_question,
    get_quick_question,
    list_quick_questions,
    mark_quick_question_used,
    reorder_quick_questions,
    update_quick_question,
)
from db.crud.table_groups import get_groups_for_user
from db.models import QuickQuestion

router = APIRouter(prefix="/api/quick-questions", tags=["快捷问题"])


class QuickQuestionCreate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    question_text: str
    table_group_id: str
    is_pinned: bool = True


class QuickQuestionUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    question_text: str | None = None
    table_group_id: str | None = None
    is_pinned: bool | None = None


class QuickQuestionReorder(BaseModel):
    ordered_ids: list[str]


class QuickQuestionOut(BaseModel):
    id: str
    display_name: str | None
    question_text: str
    table_group_id: str
    is_pinned: bool
    sort_order: int
    usage_count: int
    last_used_at: str | None
    created_at: str
    updated_at: str


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _to_out(item: QuickQuestion) -> QuickQuestionOut:
    return QuickQuestionOut(
        id=item.id,
        display_name=item.display_name,
        question_text=item.question_text,
        table_group_id=item.table_group_id,
        is_pinned=item.is_pinned,
        sort_order=item.sort_order,
        usage_count=item.usage_count,
        last_used_at=item.last_used_at.isoformat() if item.last_used_at else None,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


async def _validate_table_group_access(
    db: AsyncSession, user: UserContext, table_group_id: str | None
) -> str:
    table_group_id = _clean_text(table_group_id)
    if not table_group_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="快捷问题必须绑定表分组",
        )

    groups = await get_groups_for_user(db, user.user_id)
    if not any(group.id == table_group_id for group in groups):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无权绑定该表分组",
        )
    return table_group_id


@router.get("", response_model=list[QuickQuestionOut])
async def list_my_quick_questions(
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    items = await list_quick_questions(db, user.user_id)
    return [_to_out(item) for item in items]


@router.post("", response_model=QuickQuestionOut, status_code=status.HTTP_201_CREATED)
async def create_my_quick_question(
    body: QuickQuestionCreate,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    question_text = _clean_text(body.question_text)
    if not question_text:
        raise HTTPException(status_code=400, detail="问题文本不能为空")

    table_group_id = await _validate_table_group_access(db, user, body.table_group_id)
    item = await create_quick_question(
        db,
        user_id=user.user_id,
        display_name=_clean_text(body.display_name),
        question_text=question_text,
        table_group_id=table_group_id,
        is_pinned=body.is_pinned,
    )
    return _to_out(item)


@router.put("/{question_id}", response_model=QuickQuestionOut)
async def update_my_quick_question(
    question_id: str,
    body: QuickQuestionUpdate,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    item = await get_quick_question(db, question_id, user.user_id)
    if not item:
        raise HTTPException(status_code=404, detail="快捷问题不存在")

    display_name = ...
    if "display_name" in body.model_fields_set:
        display_name = _clean_text(body.display_name)

    question_text = None
    if "question_text" in body.model_fields_set:
        question_text = _clean_text(body.question_text)
        if not question_text:
            raise HTTPException(status_code=400, detail="问题文本不能为空")

    table_group_id = ...
    if "table_group_id" in body.model_fields_set:
        if body.table_group_id is None:
            raise HTTPException(status_code=400, detail="快捷问题必须绑定表分组")
        table_group_id = await _validate_table_group_access(db, user, body.table_group_id)

    updated = await update_quick_question(
        db,
        item,
        display_name=display_name,
        question_text=question_text,
        table_group_id=table_group_id,
        is_pinned=body.is_pinned if "is_pinned" in body.model_fields_set else None,
    )
    return _to_out(updated)


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_quick_question(
    question_id: str,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    item = await get_quick_question(db, question_id, user.user_id)
    if not item:
        raise HTTPException(status_code=404, detail="快捷问题不存在")
    await delete_quick_question(db, item)


@router.post("/reorder", response_model=list[QuickQuestionOut])
async def reorder_my_quick_questions(
    body: QuickQuestionReorder,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    items = await reorder_quick_questions(db, user.user_id, body.ordered_ids)
    return [_to_out(item) for item in items]


@router.post("/{question_id}/use", response_model=QuickQuestionOut)
async def use_my_quick_question(
    question_id: str,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    item = await get_quick_question(db, question_id, user.user_id)
    if not item:
        raise HTTPException(status_code=404, detail="快捷问题不存在")
    used = await mark_quick_question_used(db, item)
    return _to_out(used)
