"""设置相关路由"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_async_session, get_current_user
from auth.dependencies import UserContext
from auth.jwt_handler import hash_password, verify_password
from db.crud.users import get_user_by_id, update_user

router = APIRouter(prefix="/profile", tags=["设置"])


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


class ProfileOut(BaseModel):
    id: str
    email: str
    full_name: str | None
    roles: list[str]


@router.get("", response_model=ProfileOut)
async def get_profile(
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    u = await get_user_by_id(db, user.user_id)
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    return ProfileOut(id=u.id, email=u.email, full_name=u.full_name, roles=[r.name for r in u.roles])


class TableGroupOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    table_count: int


@router.get("/table-groups", response_model=list[TableGroupOut])
async def get_user_table_groups(
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """返回当前用户可访问的表分组列表（admin 用户返回全部分组）。"""
    from db.crud.table_groups import get_groups_for_user
    groups = await get_groups_for_user(db, user.user_id)
    return [
        TableGroupOut(
            id=g.id,
            name=g.name,
            description=g.description,
            table_count=len(g.tables),
        )
        for g in groups
    ]


@router.post("/change-password", status_code=204)
async def change_password(
    body: PasswordChange,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    u = await get_user_by_id(db, user.user_id)
    if not verify_password(body.old_password, u.hashed_password):
        raise HTTPException(status_code=400, detail="原密码错误")
    await update_user(db, user.user_id, hashed_password=hash_password(body.new_password))
