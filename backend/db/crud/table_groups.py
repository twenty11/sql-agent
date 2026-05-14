"""表分组 CRUD：TableGroup / TableGroupMember / role_table_groups"""

from typing import Optional
from sqlalchemy import select, insert, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    TableGroup,
    TableGroupMember,
    Role,
    role_table_groups_table,
    user_roles_table,
)


# ── 分组查询 ───────────────────────────────────────────────────

async def list_groups(db: AsyncSession) -> list[TableGroup]:
    result = await db.execute(
        select(TableGroup)
        .options(selectinload(TableGroup.tables))
        .order_by(TableGroup.name)
    )
    return list(result.scalars().all())


async def get_group(db: AsyncSession, group_id: str) -> Optional[TableGroup]:
    result = await db.execute(
        select(TableGroup)
        .where(TableGroup.id == group_id)
        .options(selectinload(TableGroup.tables))
    )
    return result.scalar_one_or_none()


async def get_group_by_name(db: AsyncSession, name: str) -> Optional[TableGroup]:
    result = await db.execute(select(TableGroup).where(TableGroup.name == name))
    return result.scalar_one_or_none()


async def count_roles_per_group(db: AsyncSession) -> dict[str, int]:
    """统计每个 group_id 下被多少角色引用。"""
    result = await db.execute(
        select(role_table_groups_table.c.group_id, func.count(role_table_groups_table.c.role_id))
        .group_by(role_table_groups_table.c.group_id)
    )
    return {row[0]: row[1] for row in result.all()}


async def list_roles_referencing_group(db: AsyncSession, group_id: str) -> list[Role]:
    result = await db.execute(
        select(Role)
        .join(role_table_groups_table, role_table_groups_table.c.role_id == Role.id)
        .where(role_table_groups_table.c.group_id == group_id)
    )
    return list(result.scalars().all())


async def list_user_ids_affected_by_group(db: AsyncSession, group_id: str) -> list[str]:
    """获取所有「绑定了引用该分组的角色」的用户 ID，用于失效 RBAC 缓存。"""
    result = await db.execute(
        select(user_roles_table.c.user_id)
        .join(
            role_table_groups_table,
            role_table_groups_table.c.role_id == user_roles_table.c.role_id,
        )
        .where(role_table_groups_table.c.group_id == group_id)
        .distinct()
    )
    return [row[0] for row in result.all()]


# ── 分组增删改 ──────────────────────────────────────────────────

async def create_group(
    db: AsyncSession, name: str, description: Optional[str] = None
) -> TableGroup:
    group = TableGroup(name=name, description=description)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group


async def update_group(
    db: AsyncSession,
    group_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[TableGroup]:
    group = await get_group(db, group_id)
    if not group:
        return None
    if name is not None:
        group.name = name
    if description is not None:
        group.description = description
    await db.commit()
    await db.refresh(group)
    return group


async def delete_group(db: AsyncSession, group_id: str) -> bool:
    group = await get_group(db, group_id)
    if not group:
        return False
    await db.delete(group)
    await db.commit()
    return True


# ── 分组-表 绑定 ────────────────────────────────────────────────

async def set_group_tables(
    db: AsyncSession,
    group_id: str,
    tables: list[dict],  # [{schema, name}, ...]
) -> list[dict]:
    """幂等覆盖分组包含的表。"""
    group = await get_group(db, group_id)
    if not group:
        return []

    await db.execute(
        delete(TableGroupMember).where(TableGroupMember.group_id == group_id)
    )

    applied: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for t in tables:
        schema = t.get("schema") or t.get("table_schema")
        name = t.get("name") or t.get("table_name")
        if not schema or not name:
            continue
        key = (schema, name)
        if key in seen:
            continue
        seen.add(key)
        db.add(TableGroupMember(group_id=group_id, table_schema=schema, table_name=name))
        applied.append({"schema": schema, "name": name})

    await db.commit()
    return applied


# ── 角色-分组 绑定 ──────────────────────────────────────────────

async def get_role_groups(db: AsyncSession, role_id: str) -> list[TableGroup]:
    result = await db.execute(
        select(TableGroup)
        .join(role_table_groups_table, role_table_groups_table.c.group_id == TableGroup.id)
        .where(role_table_groups_table.c.role_id == role_id)
        .options(selectinload(TableGroup.tables))
        .order_by(TableGroup.name)
    )
    return list(result.scalars().all())


async def set_role_groups(
    db: AsyncSession, role_id: str, group_ids: list[str]
) -> list[str]:
    """幂等覆盖某角色的可访问表分组。返回最终绑定的分组 id 列表。"""
    await db.execute(
        delete(role_table_groups_table).where(role_table_groups_table.c.role_id == role_id)
    )

    applied: list[str] = []
    if group_ids:
        existing = await db.execute(
            select(TableGroup.id).where(TableGroup.id.in_(group_ids))
        )
        valid_ids = {row[0] for row in existing.all()}
        for gid in group_ids:
            if gid in valid_ids and gid not in applied:
                await db.execute(
                    insert(role_table_groups_table).values(role_id=role_id, group_id=gid)
                )
                applied.append(gid)

    await db.commit()
    return applied


async def list_user_ids_with_role(db: AsyncSession, role_id: str) -> list[str]:
    result = await db.execute(
        select(user_roles_table.c.user_id).where(user_roles_table.c.role_id == role_id)
    )
    return [row[0] for row in result.all()]


# ── 聚合查询 ────────────────────────────────────────────────────

async def get_groups_for_user(db: AsyncSession, user_id: str) -> list[TableGroup]:
    """返回用户可访问的表分组列表。admin 用户返回所有分组，普通用户通过角色获取。"""
    result = await db.execute(
        select(Role.name)
        .join(user_roles_table, user_roles_table.c.role_id == Role.id)
        .where(user_roles_table.c.user_id == user_id)
    )
    role_names = [row[0] for row in result.all()]

    if "admin" in role_names:
        return await list_groups(db)

    result = await db.execute(
        select(TableGroup)
        .join(role_table_groups_table, role_table_groups_table.c.group_id == TableGroup.id)
        .join(user_roles_table, user_roles_table.c.role_id == role_table_groups_table.c.role_id)
        .where(user_roles_table.c.user_id == user_id)
        .options(selectinload(TableGroup.tables))
        .distinct()
        .order_by(TableGroup.name)
    )
    return list(result.scalars().all())


async def get_table_to_groups_map(db: AsyncSession) -> dict[tuple[str, str], list[dict]]:
    """返回 {(schema, table_name): [{id, name}, ...]}，供表管理界面展示所属分组。"""
    result = await db.execute(
        select(
            TableGroupMember.table_schema,
            TableGroupMember.table_name,
            TableGroup.id,
            TableGroup.name,
        ).join(TableGroup, TableGroup.id == TableGroupMember.group_id)
    )
    mapping: dict[tuple[str, str], list[dict]] = {}
    for schema, tname, gid, gname in result.all():
        mapping.setdefault((schema, tname), []).append({"id": gid, "name": gname})
    return mapping
