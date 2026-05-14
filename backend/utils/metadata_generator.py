"""
元数据生成模块 - 调用 LLM 生成表名、字段名和注释
"""
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# 导入项目根目录的 config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_settings


class ColumnMetadata(BaseModel):
    """字段元数据"""
    original_name: str = Field(description="原始字段名")
    column_name: str = Field(description="生成的英文字段名（小写下划线格式）")
    column_comment: str = Field(description="字段的中文注释说明")


class TableMetadata(BaseModel):
    """表元数据"""
    table_name: str = Field(description="生成的英文表名（小写下划线格式）")
    display_name: str = Field(description="表的中文显示名，简洁名词短语，≤15字，例如：余额调拨明细、偿付能力季报")
    table_comment: str = Field(description="表的中文注释说明，一句话描述这个表的用途和存储内容")
    columns: List[ColumnMetadata] = Field(description="字段元数据列表")


# 提示词模板
METADATA_PROMPT_TEMPLATE = """你是一个数据库设计专家。根据以下Excel/CSV数据文件的信息，生成规范的PostgreSQL数据库表名、字段名和注释。

## 文件信息
- 文件名: {file_name}
- 原始字段列表: {columns}
- 样本数据（前{sample_rows}行）:
{sample_data}

## 要求

1. **表名生成规则**:
   - 使用英文，小写字母和下划线
   - 根据文件名和数据内容推断表的用途
   - 表名要简洁且有意义，例如: insurance_company_info, solvency_report

2. **表显示名（display_name）要求**:
   - 简洁中文名词短语，15字以内，用于前端列表展示
   - 例如: "余额调拨明细"、"偿付能力季报"、"保险公司基本信息"

3. **表注释（table_comment）要求**:
   - 使用中文描述，完整一句话
   - 说明这个表是做什么的，存储什么数据
   - 例如: "保险公司基本信息表，记录各保险公司的名称、成立时间、注册资本等基本信息"

4. **字段名生成规则**:
   - 使用英文，小写字母和下划线
   - 根据原始字段名的含义进行翻译或转换
   - 字段名要简洁且有意义
   - 保持与原始字段的一一对应关系

5. **字段注释要求**:
   - 使用中文描述
   - 明确说明字段的含义和用途
   - 如果能从样本数据推断出字段的格式或取值范围，也可以说明

## 输出格式

请严格按照以下JSON格式输出，不要包含任何其他内容:

{format_instructions}
"""


def create_llm() -> ChatOpenAI:
    """创建 OpenAI 兼容的 LLM 实例"""
    settings = get_settings()

    return ChatOpenAI(
        base_url=settings.llm_base_url,
        model=settings.llm_model_name,
        api_key=settings.llm_api_key,
        temperature=0.1,
    )


def generate_table_metadata(file_info: Dict[str, Any]) -> TableMetadata:
    """
    使用大模型生成表的元数据
    
    Args:
        file_info: 文件信息字典，由 data_loader.get_file_info() 返回
        
    Returns:
        TableMetadata 对象
    """
    llm = create_llm()
    
    # 创建输出解析器
    parser = JsonOutputParser(pydantic_object=TableMetadata)
    
    # 创建提示词模板
    prompt = ChatPromptTemplate.from_template(METADATA_PROMPT_TEMPLATE)
    
    # 构建链
    chain = prompt | llm | parser
    
    # 准备输入数据
    input_data = {
        "file_name": file_info["file_name"],
        "columns": json.dumps(file_info["columns"], ensure_ascii=False),
        "sample_rows": len(file_info["sample_data"]),
        "sample_data": file_info["sample_str"],
        "format_instructions": parser.get_format_instructions(),
    }
    
    # 调用LLM
    result = chain.invoke(input_data)
    
    # 转换为Pydantic对象
    if isinstance(result, dict):
        return TableMetadata(**result)
    return result


def generate_metadata_batch(file_infos: List[Dict[str, Any]]) -> List[TableMetadata]:
    """
    批量生成多个表的元数据
    
    Args:
        file_infos: 文件信息字典列表
        
    Returns:
        TableMetadata 对象列表
    """
    results = []
    total = len(file_infos)
    
    for i, file_info in enumerate(file_infos, 1):
        file_name = file_info["file_name"]
        print(f"[{i}/{total}] 正在生成元数据: {file_name}...")
        
        try:
            metadata = generate_table_metadata(file_info)
            results.append(metadata)
            print(f"  ✓ 完成: 表名={metadata.table_name}, 字段数={len(metadata.columns)}")
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            raise
    
    return results


if __name__ == "__main__":
    test_file_info = {
        "file_name": "保险公司偿付能力数据",
        "columns": ["公司名称", "报告期", "核心偿付能力充足率", "综合偿付能力充足率"],
        "sample_data": [
            {"公司名称": "中国人寿", "报告期": "2024Q1", "核心偿付能力充足率": "150.5%", "综合偿付能力充足率": "198.5%"},
            {"公司名称": "平安人寿", "报告期": "2024Q1", "核心偿付能力充足率": "180.2%", "综合偿付能力充足率": "215.3%"},
        ],
        "sample_str": """公司名称    报告期    核心偿付能力充足率    综合偿付能力充足率
中国人寿    2024Q1    150.5%              198.5%
平安人寿    2024Q1    180.2%              215.3%"""
    }
    
    metadata = generate_table_metadata(test_file_info)
    for col in metadata.columns:
        print(col)

