"""管理员：表分组 CRUD + 分组-表 绑定

新权限模型：role → table_groups → tables
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_async_session, require_admin, get_redis
from auth.dependencies import UserContext
from auth.rbac import invalidate_users_cache
from db.crud.table_groups import (
    count_roles_per_group,
    create_group,
    delete_group,
    get_group,
    get_group_by_name,
    list_groups,
    list_roles_referencing_group,
    list_user_ids_affected_by_group,
    set_group_tables,
    update_group,
)

router = APIRouter(prefix="/admin/table-groups", tags=["管理员-表分组"])


# ── Schemas ───────────────────────────────────────────────────

class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class GroupOut(BaseModel):
    id: str
    name: str
    description: str | None
    table_count: int
    role_count: int


class TableRef(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    table_schema: str = Field(alias="schema")
    name: str


class GroupDetailOut(GroupOut):
    tables: list[TableRef]


class TablesUpdate(BaseModel):
    tables: list[TableRef] = Field(default_factory=list)


# ── Endpoints ──────────────────────────────────────────────────

@router.get("", response_model=list[GroupOut])
async def list_all_groups(
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
):
    groups = await list_groups(db)
    role_counts = await count_roles_per_group(db)
    return [
        GroupOut(
            id=g.id,
            name=g.name,
            description=g.description,
            table_count=len(g.tables),
            role_count=role_counts.get(g.id, 0),
        )
        for g in groups
    ]


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
async def create_new_group(
    body: GroupCreate,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
):
    if await get_group_by_name(db, body.name):
        raise HTTPException(status_code=400, detail="分组名已存在")
    group = await create_group(db, body.name, body.description)
    return GroupOut(
        id=group.id,
        name=group.name,
        description=group.description,
        table_count=0,
        role_count=0,
    )


@router.get("/{group_id}", response_model=GroupDetailOut, response_model_by_alias=True)
async def get_group_detail(
    group_id: str,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
):
    group = await get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    role_counts = await count_roles_per_group(db)
    return GroupDetailOut(
        id=group.id,
        name=group.name,
        description=group.description,
        table_count=len(group.tables),
        role_count=role_counts.get(group.id, 0),
        tables=[
            TableRef(schema=m.table_schema, name=m.table_name) for m in group.tables
        ],
    )


@router.put("/{group_id}", response_model=GroupOut)
async def update_existing_group(
    group_id: str,
    body: GroupUpdate,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
):
    group = await get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    if body.name and body.name != group.name:
        other = await get_group_by_name(db, body.name)
        if other and other.id != group_id:
            raise HTTPException(status_code=400, detail="分组名已存在")
    group = await update_group(db, group_id, name=body.name, description=body.description)
    role_counts = await count_roles_per_group(db)
    return GroupOut(
        id=group.id,
        name=group.name,
        description=group.description,
        table_count=len(group.tables),
        role_count=role_counts.get(group.id, 0),
    )


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_group(
    group_id: str,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
    redis=Depends(get_redis),
):
    group = await get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")

    referencing = await list_roles_referencing_group(db, group_id)
    if referencing:
        names = "、".join(r.name for r in referencing)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"该分组正被角色引用（{names}），请先在相关角色中取消引用",
        )

    affected_users = await list_user_ids_affected_by_group(db, group_id)
    await delete_group(db, group_id)
    await invalidate_users_cache(affected_users, redis)


@router.get("/{group_id}/tables", response_model=list[TableRef], response_model_by_alias=True)
async def get_group_tables(
    group_id: str,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
):
    group = await get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    return [TableRef(schema=m.table_schema, name=m.table_name) for m in group.tables]


@router.put("/{group_id}/tables", response_model=list[TableRef], response_model_by_alias=True)
async def update_group_tables(
    group_id: str,
    body: TablesUpdate,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_async_session),
    redis=Depends(get_redis),
):
    group = await get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")

    # 失效前先记录受影响用户
    affected_users = await list_user_ids_affected_by_group(db, group_id)
    applied = await set_group_tables(
        db, group_id, [t.model_dump(by_alias=True) for t in body.tables]
    )
    await invalidate_users_cache(affected_users, redis)

    return [TableRef(**a) for a in applied]
