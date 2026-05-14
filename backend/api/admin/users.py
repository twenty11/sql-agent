"""管理员用户管理路由"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_async_session, require_admin, get_redis
from auth.dependencies import UserContext
from auth.jwt_handler import hash_password
from auth.rbac import invalidate_user_cache
from db.crud.users import (
    get_user_by_email, create_user, list_users, set_user_active,
    get_user_by_id, delete_user, update_user,
)
from db.crud.roles import assign_role_to_user, set_user_roles
from db.models import RefreshToken

router = APIRouter(prefix="/admin/users", tags=["管理员-用户"])


# ── Schemas ───────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str | None = None
    # 支持多角色；保留 role 字段向后兼容单角色调用
    roles: list[str] | None = None
    role: str | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    password: str | None = Field(default=None, min_length=6)


class RolesUpdate(BaseModel):
    roles: list[str] = Field(default_factory=list)


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str | None
    is_active: bool
    roles: list[str]
    created_at: str


class ActiveToggle(BaseModel):
    is_active: bool


def _to_out(u) -> UserOut:
    return UserOut(
        id=u.id, email=u.email, full_name=u.full_name,
        is_active=u.is_active, roles=[r.name for r in u.roles],
        created_at=u.created_at.isoformat(),
    )


# ── Endpoints ──────────────────────────────────────────────────

@router.get("", response_model=list[UserOut])
async def list_all_users(
    skip: int = 0,
    limit: int = 100,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
):
    users = await list_users(db, skip=skip, limit=limit)
    return [_to_out(u) for u in users]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_new_user(
    body: UserCreate,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
):
    existing = await get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    u = await create_user(db, body.email, hash_password(body.password), body.full_name)

    role_names = body.roles if body.roles is not None else (
        [body.role] if body.role else ["viewer"]
    )
    await set_user_roles(db, u.id, role_names)

    u = await get_user_by_id(db, u.id)
    return _to_out(u)


@router.put("/{user_id}", response_model=UserOut)
async def update_existing_user(
    user_id: str,
    body: UserUpdate,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
):
    u = await update_user(
        db, user_id,
        full_name=body.full_name,
        hashed_password=hash_password(body.password) if body.password else None,
    )
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    u = await get_user_by_id(db, user_id)
    return _to_out(u)


@router.put("/{user_id}/active", response_model=UserOut)
async def toggle_user_active(
    user_id: str,
    body: ActiveToggle,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
):
    u = await set_user_active(db, user_id, body.is_active)
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 禁用时撤销所有未过期的 refresh token，立即使现存会话失效
    if not body.is_active:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked == False)
            .values(revoked=True)
        )
        await db.commit()

    return _to_out(u)


@router.put("/{user_id}/roles", response_model=UserOut)
async def update_user_roles(
    user_id: str,
    body: RolesUpdate,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
    redis=Depends(get_redis),
):
    """覆盖用户全部角色。变更后失效该用户的表权限缓存。"""
    u = await get_user_by_id(db, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")

    await set_user_roles(db, user_id, body.roles)
    await invalidate_user_cache(user_id, redis)

    u = await get_user_by_id(db, user_id)
    return _to_out(u)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user(
    user_id: str,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
    redis=Depends(get_redis),
):
    try:
        ok = await delete_user(db, user_id)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户存在受限关联记录，无法删除；可改为禁用该用户",
        )
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    await invalidate_user_cache(user_id, redis)
