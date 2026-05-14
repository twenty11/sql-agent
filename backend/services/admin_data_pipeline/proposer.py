"""
Proposer：LLM 调用层。

核心约束（命名稳定性原则）：
  - 绝对不为已存在于 meta.logical_columns 的 original_name 重新生成 physical_name。
  - 全新表对全部字段调用 LLM。
  - 已有表 schema_change 仅对新增字段调用 LLM。
"""

import re
from typing import Any, Dict, Sequence

from utils.metadata_generator import create_llm, METADATA_PROMPT_TEMPLATE, TableMetadata
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import json


def sanitize_column_name(name: str) -> str:
    """中文/特殊字符转安全 snake_case（fallback，当 LLM 未返回时使用）。"""
    safe = re.sub(r"[^\w\s]", "", name)
    safe = safe.replace(" ", "_").lower().strip("_")
    if safe and safe[0].isdigit():
        safe = "col_" + safe
    return safe or "unknown_column"


def propose_for_new_table(
    file_info: Dict[str, Any],
    forbidden_table_names: Sequence[str] | None = None,
) -> TableMetadata:
    """
    为全新表调用 LLM，生成表名、表注释和所有字段的 physical_name + 注释。
    复用 metadata_generator.py 的 LLM chain，保持 prompt 一致性。
    """
    llm = create_llm()
    parser = JsonOutputParser(pydantic_object=TableMetadata)
    prompt_template = METADATA_PROMPT_TEMPLATE
    if forbidden_table_names:
        names = ", ".join(sorted(set(forbidden_table_names)))
        prompt_template += (
            "\n\n## 已存在表名限制\n"
            f"当前分组下已经存在以下 PostgreSQL 物理表名，生成 table_name 时禁止使用这些名称: {names}\n"
            "如果语义相近，请生成一个仍能表达业务含义、但不在上述列表中的新表名。\n"
        )
    prompt = ChatPromptTemplate.from_template(prompt_template)
    chain = prompt | llm | parser

    result = chain.invoke({
        "file_name": file_info["file_name"],
        "columns": json.dumps(file_info["columns"], ensure_ascii=False),
        "sample_rows": len(file_info.get("sample_data", [])),
        "sample_data": file_info.get("sample_str", ""),
        "format_instructions": parser.get_format_instructions(),
    })

    if isinstance(result, dict):
        return TableMetadata(**result)
    return result


def propose_for_new_columns(
    file_info: Dict[str, Any],
    new_columns: Sequence[str],
) -> TableMetadata:
    """
    为已有表更新中出现的新增字段调用 LLM。

    只把新增字段提交给 LLM，避免重新生成已有字段的物理列名，保持旧字段映射稳定。
    返回结构沿用 TableMetadata，调用方只读取 columns。
    """
    new_columns = [str(c) for c in new_columns]
    sample_data = file_info.get("sample_data", [])
    sample_df_rows = [
        {col: row.get(col) for col in new_columns if col in row}
        for row in sample_data
        if isinstance(row, dict)
    ]
    sample_str = ""
    if sample_df_rows:
        try:
            import pandas as pd

            sample_str = pd.DataFrame(sample_df_rows, columns=new_columns).to_string(index=False)
        except Exception:
            sample_str = json.dumps(sample_df_rows, ensure_ascii=False)

    focused_file_info = {
        **file_info,
        "columns": new_columns,
        "sample_data": sample_df_rows,
        "sample_str": sample_str or file_info.get("sample_str", ""),
    }
    return propose_for_new_table(focused_file_info)
