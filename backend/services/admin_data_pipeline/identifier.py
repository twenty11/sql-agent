"""
Identifier：根据文件信息和可选的 target_table_id 判断 action_type。

- new_table  → 目标表在 meta.logical_tables 中不存在
- data_only  → 目标表存在，上传文件没有新增列（允许少列）
- schema_change → 目标表存在，上传文件包含新增列
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class ActionDecision:
    action_type: str                          # new_table / data_only / schema_change
    table_id: Optional[str]                   # None for new_table
    # mapping: original_name → existing MetaLogicalColumn dict (for existing cols)
    existing_col_map: Dict[str, dict] = field(default_factory=dict)


async def decide_action(
    session: AsyncSession,
    file_info: dict,
    target_table_id: Optional[str] = None,
) -> ActionDecision:
    """
    确定本次上传的操作类型。

    Args:
        session:          异步数据库会话
        file_info:        data_loader.get_file_info 的返回值
        target_table_id:  admin 在前端明确指定的目标表 ID（可选）

    Raises:
        ValueError: 当 target_table_id 指定的表无法读取时抛出。
    """
    file_columns: List[str] = file_info.get("columns", [])

    if target_table_id:
        return await _check_existing(session, target_table_id, file_columns)

    return ActionDecision(action_type="new_table", table_id=None)


async def _check_existing(
    session: AsyncSession,
    table_id: str,
    file_columns: List[str],
) -> ActionDecision:
    """检查目标表的现有列集合，存在新增列则返回 schema_change，否则 data_only。"""
    rows = await session.execute(text("""
        SELECT id, original_name, physical_name, column_comment,
               ordinal_position, data_type
        FROM meta.logical_columns
        WHERE table_id = :tid AND is_active = true
        ORDER BY ordinal_position
    """), {"tid": table_id})
    existing_cols = {r.original_name: dict(r._mapping) for r in rows.fetchall()}

    file_col_set = {str(c) for c in file_columns}
    existing_col_set = set(existing_cols.keys())

    return ActionDecision(
        action_type="schema_change" if file_col_set - existing_col_set else "data_only",
        table_id=table_id,
        existing_col_map=existing_cols,
    )
