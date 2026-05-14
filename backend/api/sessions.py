"""会话管理路由"""

from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_async_session, get_current_user, get_redis
from auth.dependencies import UserContext
from db.crud.sessions import (
    create_session, get_sessions_for_user, get_session,
    update_session_title, delete_session
)
from db.crud.messages import get_messages_by_session
from services.query_runs import reconcile_streaming_messages
from graph.nodes import get_llm
from graph.prompts import TITLE_GENERATION_PROMPT

router = APIRouter(prefix="/api/sessions", tags=["会话管理"])


class SessionCreate(BaseModel):
    title: str = "新对话"


class SessionUpdate(BaseModel):
    title: str


class SessionOut(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    metadata: dict | None = None
    created_at: str


@router.get("", response_model=list[SessionOut])
async def list_sessions(
    skip: int = 0,
    limit: int = 50,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    sessions = await get_sessions_for_user(db, user.user_id, skip=skip, limit=limit)
    return [
        SessionOut(
            id=s.id,
            title=s.title,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
        )
        for s in sessions
    ]


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_new_session(
    body: SessionCreate,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    s = await create_session(db, user.user_id, title=body.title)
    return SessionOut(id=s.id, title=s.title, created_at=s.created_at.isoformat(), updated_at=s.updated_at.isoformat())


@router.put("/{session_id}", response_model=SessionOut)
async def rename_session(
    session_id: str,
    body: SessionUpdate,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    s = await get_session(db, session_id)
    if not s or s.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="会话不存在")
    s = await update_session_title(db, session_id, body.title, mark_user_renamed=True)
    return SessionOut(id=s.id, title=s.title, created_at=s.created_at.isoformat(), updated_at=s.updated_at.isoformat())


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_session(
    session_id: str,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    s = await get_session(db, session_id)
    if not s or s.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="会话不存在")
    await delete_session(db, session_id)


class TitleOut(BaseModel):
    title: str


@router.post("/{session_id}/generate-title", response_model=TitleOut)
async def generate_session_title(
    session_id: str,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """在第一轮 Q&A 完成后，基于用户问题+助手回复自动生成会话标题。
    若用户已手动重命名（auto_titled=False），直接返回当前标题不覆盖。
    """
    s = await get_session(db, session_id)
    if not s or s.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="会话不存在")

    if not s.auto_titled:
        return TitleOut(title=s.title)

    # 标题已自动生成（非默认值），直接返回，避免重复调用 LLM
    if s.title != "新对话":
        return TitleOut(title=s.title)

    msgs = await get_messages_by_session(db, session_id, limit=10)
    user_msg = next((m for m in msgs if m.role == "user"), None)
    assistant_msg = next((m for m in msgs if m.role == "assistant"), None)

    if not user_msg or not assistant_msg:
        return TitleOut(title=s.title)

    try:
        chain = TITLE_GENERATION_PROMPT | get_llm() | StrOutputParser()
        title = await chain.ainvoke({
            "question": user_msg.content,
            "answer": assistant_msg.content[:500],
        })
        title = title.strip()[:30] or s.title
        await update_session_title(db, session_id, title)
    except Exception as e:
        print(f"[标题生成] 失败 session={session_id}: {e}")
        title = s.title

    return TitleOut(title=title)


@router.get("/{session_id}/messages", response_model=list[MessageOut])
async def list_session_messages(
    session_id: str,
    limit: int = 100,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """获取指定会话的历史消息，按时间升序返回"""
    s = await get_session(db, session_id)
    if not s or s.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="会话不存在")
    msgs = await get_messages_by_session(db, session_id, limit=limit)
    msgs = await reconcile_streaming_messages(get_redis(), msgs)
    return [
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            metadata=m.metadata_,
            created_at=m.created_at.isoformat(),
        )
        for m in msgs
    ]
