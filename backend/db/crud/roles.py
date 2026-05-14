"""角色和权限 CRUD 操作"""

from typing import Optional
from sqlalchemy import select, insert, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    Role, Permission, User, TableGroup, TableGroupMember,
    user_roles_table, role_permissions_table, role_table_groups_table,
)


# 内置角色（不允许删除/重命名）
BUILTIN_ROLES = {"admin", "analyst", "viewer"}


# ──────────────────────────────────────────────────────────────
# 查询
# ──────────────────────────────────────────────────────────────

async def get_role_by_id(db: AsyncSession, role_id: str) -> Optional[Role]:
    result = await db.execute(
        select(Role).where(Role.id == role_id).options(selectinload(Role.permissions))
    )
    return result.scalar_one_or_none()


async def get_role_by_name(db: AsyncSession, name: str) -> Optional[Role]:
    result = await db.execute(
        select(Role).where(Role.name == name).options(selectinload(Role.permissions))
    )
    return result.scalar_one_or_none()


async def get_roles_for_user(db: AsyncSession, user_id: str) -> list[Role]:
    result = await db.execute(
        select(Role)
        .join(user_roles_table, user_roles_table.c.role_id == Role.id)
        .where(user_roles_table.c.user_id == user_id)
        .options(selectinload(Role.permissions))
    )
    return list(result.scalars().all())


async def get_allowed_tables_for_user(db: AsyncSession, user_id: str) -> Optional[list[str]]:
    """
    获取用户的可访问表白名单。

    返回：
      - None   → admin 角色，无限制
      - list  → 显式白名单；空列表 `[]` 表示该用户不允许访问任何表

    非-admin 用户的白名单 = 其所有角色绑定的 TableGroup 内所有成员表的并集。
    """
    result = await db.execute(
        select(Role)
        .join(user_roles_table, user_roles_table.c.role_id == Role.id)
        .where(user_roles_table.c.user_id == user_id)
        .options(
            selectinload(Role.table_groups).selectinload(TableGroup.tables)
        )
    )
    roles = list(result.scalars().all())

    for role in roles:
        if role.name == "admin":
            return None

    table_names: set[str] = set()
    for role in roles:
        for group in role.table_groups:
            for member in group.tables:
                table_names.add(member.table_name)

    return sorted(table_names)


async def list_roles(db: AsyncSession) -> list[Role]:
    result = await db.execute(
        select(Role).options(selectinload(Role.permissions))
    )
    return list(result.scalars().all())


async def get_role_table_permissions(db: AsyncSession, role_id: str) -> list[str]:
    """返回该角色拥有 read 权限的所有表名。"""
    role = await get_role_by_id(db, role_id)
    if not role:
        return []
    return sorted(
        p.resource_name for p in role.permissions
        if p.resource_type == "table" and p.action == "read"
    )


async def count_users_per_role(db: AsyncSession) -> dict[str, int]:
    """统计每个 role_id 下的用户数。"""
    from sqlalchemy import func
    result = await db.execute(
        select(user_roles_table.c.role_id, func.count(user_roles_table.c.user_id))
        .group_by(user_roles_table.c.role_id)
    )
    return {row[0]: row[1] for row in result.all()}


# ──────────────────────────────────────────────────────────────
# 角色 CRUD
# ──────────────────────────────────────────────────────────────

async def create_role(
    db: AsyncSession,
    name: str,
    description: Optional[str] = None,
) -> Role:
    role = Role(name=name, description=description)
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return role


async def update_role(
    db: AsyncSession,
    role_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[Role]:
    role = await get_role_by_id(db, role_id)
    if not role:
        return None
    if name is not None and role.name not in BUILTIN_ROLES:
        role.name = name
    if description is not None:
        role.description = description
    await db.commit()
    await db.refresh(role)
    return role


async def delete_role(db: AsyncSession, role_id: str) -> tuple[bool, str]:
    """删除角色；返回 (是否成功, 失败原因)。内置角色不可删除。"""
    role = await get_role_by_id(db, role_id)
    if not role:
        return False, "角色不存在"
    if role.name in BUILTIN_ROLES:
        return False, f"内置角色 '{role.name}' 不可删除"
    await db.delete(role)
    await db.commit()
    return True, ""


# ──────────────────────────────────────────────────────────────
# 用户-角色绑定
# ──────────────────────────────────────────────────────────────

async def assign_role_to_user(db: AsyncSession, user_id: str, role_name: str) -> bool:
    role_result = await db.execute(select(Role).where(Role.name == role_name))
    role = role_result.scalar_one_or_none()
    if not role:
        return False
    # 幂等：避免重复插入导致主键冲突
    existing = await db.execute(
        select(user_roles_table).where(
            user_roles_table.c.user_id == user_id,
            user_roles_table.c.role_id == role.id,
        )
    )
    if not existing.first():
        await db.execute(
            insert(user_roles_table).values(user_id=user_id, role_id=role.id)
        )
    await db.commit()
    return True


async def remove_role_from_user(db: AsyncSession, user_id: str, role_id: str) -> bool:
    await db.execute(
        delete(user_roles_table).where(
            user_roles_table.c.user_id == user_id,
            user_roles_table.c.role_id == role_id,
        )
    )
    await db.commit()
    return True


async def set_user_roles(db: AsyncSession, user_id: str, role_names: list[str]) -> list[str]:
    """用 role_names 覆盖该用户全部角色。返回最终生效的角色名列表（过滤掉不存在的角色）。"""
    # 清空现有绑定
    await db.execute(
        delete(user_roles_table).where(user_roles_table.c.user_id == user_id)
    )

    if role_names:
        rows = await db.execute(
            select(Role).where(Role.name.in_(role_names))
        )
        roles = list(rows.scalars().all())
        for role in roles:
            await db.execute(
                insert(user_roles_table).values(user_id=user_id, role_id=role.id)
            )
        await db.commit()
        return [r.name for r in roles]

    await db.commit()
    return []


# ──────────────────────────────────────────────────────────────
# 角色-表权限 绑定
# ──────────────────────────────────────────────────────────────

async def add_permission_to_role(
    db: AsyncSession,
    role_id: str,
    resource_type: str,
    resource_name: str,
    action: str = "read",
) -> Permission:
    result = await db.execute(
        select(Permission).where(
            Permission.resource_type == resource_type,
            Permission.resource_name == resource_name,
            Permission.action == action,
        )
    )
    perm = result.scalar_one_or_none()
    if not perm:
        perm = Permission(resource_type=resource_type, resource_name=resource_name, action=action)
        db.add(perm)
        await db.flush()

    existing = await db.execute(
        select(role_permissions_table).where(
            role_permissions_table.c.role_id == role_id,
            role_permissions_table.c.permission_id == perm.id,
        )
    )
    if not existing.first():
        await db.execute(
            insert(role_permissions_table).values(role_id=role_id, permission_id=perm.id)
        )

    await db.commit()
    return perm


async def set_role_table_permissions(
    db: AsyncSession,
    role_id: str,
    table_names: list[str],
    action: str = "read",
) -> list[str]:
    """用 table_names 覆盖该角色的全部 table/read 权限。返回最终生效的表名列表。"""
    role = await get_role_by_id(db, role_id)
    if not role:
        return []

    # 1) 解绑该角色当前所有 table/read 权限关联
    current_perm_ids = [
        p.id for p in role.permissions
        if p.resource_type == "table" and p.action == action
    ]
    if current_perm_ids:
        await db.execute(
            delete(role_permissions_table).where(
                role_permissions_table.c.role_id == role_id,
                role_permissions_table.c.permission_id.in_(current_perm_ids),
            )
        )

    # 2) 为每个目标表 upsert permission 记录并绑定到角色
    applied: list[str] = []
    for tname in sorted(set(table_names)):
        r = await db.execute(
            select(Permission).where(
                Permission.resource_type == "table",
                Permission.resource_name == tname,
                Permission.action == action,
            )
        )
        perm = r.scalar_one_or_none()
        if not perm:
            perm = Permission(resource_type="table", resource_name=tname, action=action)
            db.add(perm)
            await db.flush()

        await db.execute(
            insert(role_permissions_table).values(role_id=role_id, permission_id=perm.id)
        )
        applied.append(tname)

    await db.commit()
    return applied


async def list_user_ids_with_role(db: AsyncSession, role_id: str) -> list[str]:
    result = await db.execute(
        select(user_roles_table.c.user_id).where(user_roles_table.c.role_id == role_id)
    )
    return [row[0] for row in result.all()]
