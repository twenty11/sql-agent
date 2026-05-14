"""管理员角色与角色-表权限管理路由"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_async_session, require_admin, get_redis
from auth.dependencies import UserContext
from auth.rbac import invalidate_users_cache
from db.crud.roles import (
    BUILTIN_ROLES,
    count_users_per_role,
    create_role,
    delete_role,
    get_role_by_id,
    get_role_by_name,
    list_roles,
    list_user_ids_with_role,
    update_role,
)
from db.crud.table_groups import (
    get_role_groups,
    set_role_groups,
)

router = APIRouter(prefix="/admin/roles", tags=["管理员-角色"])


# ── Schemas ───────────────────────────────────────────────────

class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str | None = None


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class RoleOut(BaseModel):
    id: str
    name: str
    description: str | None
    is_builtin: bool
    group_count: int   # 可访问表分组数
    user_count: int


class GroupRef(BaseModel):
    id: str
    name: str
    description: str | None
    table_count: int


class RoleDetailOut(RoleOut):
    groups: list[GroupRef]


class GroupsUpdate(BaseModel):
    group_ids: list[str] = Field(default_factory=list)


# ── Endpoints ──────────────────────────────────────────────────

def _to_out(role, user_count: int, group_count: int) -> RoleOut:
    return RoleOut(
        id=role.id,
        name=role.name,
        description=role.description,
        is_builtin=role.name in BUILTIN_ROLES,
        group_count=group_count,
        user_count=user_count,
    )


async def _group_counts_by_role(db: AsyncSession) -> dict[str, int]:
    from sqlalchemy import select, func
    from db.models import role_table_groups_table
    result = await db.execute(
        select(role_table_groups_table.c.role_id, func.count(role_table_groups_table.c.group_id))
        .group_by(role_table_groups_table.c.role_id)
    )
    return {row[0]: row[1] for row in result.all()}


@router.get("", response_model=list[RoleOut])
async def list_all_roles(
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
):
    roles = await list_roles(db)
    user_counts = await count_users_per_role(db)
    group_counts = await _group_counts_by_role(db)
    return [
        _to_out(r, user_counts.get(r.id, 0), group_counts.get(r.id, 0))
        for r in roles
    ]


@router.post("", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
async def create_new_role(
    body: RoleCreate,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
):
    existing = await get_role_by_name(db, body.name)
    if existing:
        raise HTTPException(status_code=400, detail="角色名已存在")
    role = await create_role(db, body.name, body.description)
    role = await get_role_by_id(db, role.id)
    return _to_out(role, 0, 0)


@router.get("/{role_id}", response_model=RoleDetailOut)
async def get_role_detail(
    role_id: str,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
):
    role = await get_role_by_id(db, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    user_counts = await count_users_per_role(db)
    groups = await get_role_groups(db, role_id)
    group_refs = [
        GroupRef(id=g.id, name=g.name, description=g.description, table_count=len(g.tables))
        for g in groups
    ]
    base = _to_out(role, user_counts.get(role.id, 0), len(groups))
    return RoleDetailOut(**base.model_dump(), groups=group_refs)


@router.put("/{role_id}", response_model=RoleOut)
async def update_existing_role(
    role_id: str,
    body: RoleUpdate,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
):
    role = await get_role_by_id(db, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    if body.name and body.name != role.name:
        if role.name in BUILTIN_ROLES:
            raise HTTPException(status_code=400, detail=f"内置角色 '{role.name}' 不可重命名")
        existing = await get_role_by_name(db, body.name)
        if existing and existing.id != role_id:
            raise HTTPException(status_code=400, detail="角色名已存在")

    role = await update_role(db, role_id, name=body.name, description=body.description)
    user_counts = await count_users_per_role(db)
    group_counts = await _group_counts_by_role(db)
    return _to_out(role, user_counts.get(role.id, 0), group_counts.get(role.id, 0))


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_role(
    role_id: str,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
    redis=Depends(get_redis),
):
    # 删除前记录受影响的用户，用于失效缓存
    affected_users = await list_user_ids_with_role(db, role_id)
    ok, reason = await delete_role(db, role_id)
    if not ok:
        if reason == "角色不存在":
            raise HTTPException(status_code=404, detail=reason)
        raise HTTPException(status_code=400, detail=reason)
    await invalidate_users_cache(affected_users, redis)


@router.get("/{role_id}/table-groups", response_model=list[GroupRef])
async def get_role_table_groups(
    role_id: str,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
):
    role = await get_role_by_id(db, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    groups = await get_role_groups(db, role_id)
    return [
        GroupRef(
            id=g.id,
            name=g.name,
            description=g.description,
            table_count=len(g.tables),
        )
        for g in groups
    ]


@router.put("/{role_id}/table-groups", response_model=list[str])
async def update_role_table_groups(
    role_id: str,
    body: GroupsUpdate,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
    redis=Depends(get_redis),
):
    """覆盖角色绑定的表分组。admin 角色可配置但不生效（admin 始终无限制）。"""
    role = await get_role_by_id(db, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    applied = await set_role_groups(db, role_id, body.group_ids)
    affected_users = await list_user_ids_with_role(db, role_id)
    await invalidate_users_cache(affected_users, redis)
    return applied
