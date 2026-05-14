"""
JSON配置生成模块 - 将元数据保存为JSON文件
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from utils.metadata_generator import TableMetadata, ColumnMetadata

DEFAULT_SCHEMAS_DIR = Path(__file__).parent / "output/schemas"

def create_schema_dict(
    file_info: Dict[str, Any],
    metadata: TableMetadata
) -> Dict[str, Any]:
    """
    创建JSON配置字典
    
    Args:
        file_info: 文件信息字典，由 data_loader.get_file_info() 返回
        metadata: 大模型生成的表元数据
        
    Returns:
        JSON配置字典
    """
    # 构建字段映射，确保原始字段和新字段一一对应
    columns_config = []
    
    # 创建原始字段名到元数据的映射
    metadata_map = {col.original_name: col for col in metadata.columns}
    
    for original_name in file_info["columns"]:
        if original_name in metadata_map:
            col_meta = metadata_map[original_name]
            columns_config.append({
                "original_name": original_name,
                "column_name": col_meta.column_name,
                "column_comment": col_meta.column_comment,
                "data_type": "TEXT"  # 根据需求，全部使用TEXT类型
            })
        else:
            # 如果大模型漏掉了某个字段，使用默认值
            columns_config.append({
                "original_name": original_name,
                "column_name": _sanitize_column_name(original_name),
                "column_comment": original_name,
                "data_type": "TEXT"
            })
    
    return {
        "source_file": file_info["file_path"],
        "table_name": metadata.table_name,
        "display_name": metadata.display_name,
        "table_comment": metadata.table_comment,
        "columns": columns_config,
        "created_at": datetime.now().isoformat(),
    }


def _sanitize_column_name(name: str) -> str:
    """
    将字段名转换为安全的PostgreSQL字段名
    
    Args:
        name: 原始字段名
        
    Returns:
        安全的字段名
    """
    import re
    # 移除特殊字符，替换空格为下划线
    safe_name = re.sub(r'[^\w\s]', '', name)
    safe_name = safe_name.replace(' ', '_').lower()
    # 如果以数字开头，添加前缀
    if safe_name and safe_name[0].isdigit():
        safe_name = 'col_' + safe_name
    return safe_name or 'unknown_column'


def save_schema_to_json(
    schema_dict: Dict[str, Any],
    output_dir: Optional[str | Path] = None,
    file_name: Optional[str] = None
) -> Path:
    """
    将配置字典保存为JSON文件
    
    Args:
        schema_dict: JSON配置字典
        output_dir: 输出目录，默认为 DEFAULT_SCHEMAS_DIR
        file_name: 输出文件名（不含扩展名），默认使用表名
        
    Returns:
        保存的文件路径
    """
    if output_dir is None:
        output_dir = DEFAULT_SCHEMAS_DIR
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if file_name is None:
        file_name = schema_dict["table_name"]
    
    output_path = output_dir / f"{file_name}.json"
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema_dict, f, ensure_ascii=False, indent=2)
    
    return output_path


def load_schema_from_json(json_path: str | Path) -> Dict[str, Any]:
    """
    从JSON文件加载配置
    
    Args:
        json_path: JSON文件路径
        
    Returns:
        JSON配置字典
    """
    json_path = Path(json_path)
    
    if not json_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {json_path}")
    
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_all_schemas(schema_dir: Optional[str | Path] = None) -> List[Dict[str, Any]]:
    """
    加载目录下的所有JSON配置文件
    
    Args:
        schema_dir: 配置文件目录，默认为 DEFAULT_SCHEMAS_DIR
        
    Returns:
        配置字典列表
    """
    if schema_dir is None:
        schema_dir = DEFAULT_SCHEMAS_DIR
    
    schema_dir = Path(schema_dir)
    
    if not schema_dir.exists():
        return []
    
    schemas = []
    for json_file in sorted(schema_dir.glob("*.json")):
        try:
            schema = load_schema_from_json(json_file)
            schemas.append(schema)
        except Exception as e:
            print(f"警告: 加载 {json_file.name} 失败: {e}")
    
    return schemas



def generate_and_save_schema(
    file_info: Dict[str, Any],
    metadata: TableMetadata,
    output_dir: Optional[str | Path] = None
) -> Path:
    """
    生成JSON配置并保存到文件
    
    Args:
        file_info: 文件信息字典
        metadata: 表元数据
        output_dir: 输出目录
        
    Returns:
        保存的文件路径
    """
    schema_dict = create_schema_dict(file_info, metadata)
    return save_schema_to_json(schema_dict, output_dir)


if __name__ == "__main__":
    # 测试代码
    from metadata_generator import TableMetadata, ColumnMetadata
    
    # 模拟文件信息
    test_file_info = {
        "file_path": "D:/data/保险公司偿付能力数据.xlsx",
        "file_name": "保险公司偿付能力数据",
        "columns": ["公司名称", "报告期", "核心偿付能力充足率", "综合偿付能力充足率"],
    }
    
    # 模拟元数据
    test_metadata = TableMetadata(
        table_name="insurance_solvency_data",
        table_comment="保险公司偿付能力季度报告数据表，记录各保险公司的偿付能力充足率指标",
        columns=[
            ColumnMetadata(original_name="公司名称", column_name="company_name", column_comment="保险公司名称"),
            ColumnMetadata(original_name="报告期", column_name="report_period", column_comment="报告期间，如2024Q1"),
            ColumnMetadata(original_name="核心偿付能力充足率", column_name="core_solvency_ratio", column_comment="核心偿付能力充足率"),
            ColumnMetadata(original_name="综合偿付能力充足率", column_name="comprehensive_solvency_ratio", column_comment="综合偿付能力充足率"),
        ]
    )
    
    # 生成配置
    schema = create_schema_dict(test_file_info, test_metadata)
    print("生成的JSON配置:")
    print(json.dumps(schema, ensure_ascii=False, indent=2))

