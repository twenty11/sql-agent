"""
数据读取模块 - 扫描和读取Excel/CSV数据文件
"""
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd


CSV_ENCODINGS = ["utf-8-sig", "utf-8", "gb18030", "gbk", "gb2312"]


def scan_data_files(folder_path: str) -> List[Path]:
    """
    递归扫描文件夹，返回所有支持的数据文件路径列表
    
    Args:
        folder_path: 文件夹路径
        
    Returns:
        数据文件路径列表
    """
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"文件夹不存在: {folder_path}")
    
    if not folder.is_dir():
        raise ValueError(f"路径不是文件夹: {folder_path}")
    
    data_files = []
    for ext in [".xlsx", ".xls", ".csv"]:
        # 递归查找所有匹配的文件
        data_files.extend(folder.rglob(f"*{ext}"))
    
    # 按文件名排序
    data_files.sort(key=lambda x: x.name)
    
    return data_files


def read_csv_with_encoding(
    file_path: Path,
    header: int | None = 0,
    nrows: Optional[int] = None,
) -> pd.DataFrame:
    """
    尝试使用不同编码读取CSV文件
    
    Args:
        file_path: CSV文件路径
        
    Returns:
        DataFrame
    """
    last_error = None
    for encoding in CSV_ENCODINGS:
        try:
            df = pd.read_csv(file_path, encoding=encoding, header=header, nrows=nrows)
            return df
        except (UnicodeDecodeError, UnicodeError) as e:
            last_error = e
            continue
    
    raise ValueError(f"无法读取CSV文件 {file_path}，尝试的编码: {CSV_ENCODINGS}。错误: {last_error}")


def detect_header_row(file_path: str | Path, max_scan_rows: int = 20) -> int:
    """
    自动检测列头行的位置
    
    检测策略：
    1. 列头行通常是字符串类型
    2. 列头行的非空值比例较高
    3. 列头行的下一行开始是数据（可能包含数字）
    4. 列头行通常没有重复值（列名应该唯一）
    
    Args:
        file_path: 文件路径
        max_scan_rows: 最多扫描的行数
        
    Returns:
        列头行的索引（0-based）
    """
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()
    
    # 先读取前 max_scan_rows 行，不指定 header
    if suffix == ".csv":
        df_raw = read_csv_with_encoding(file_path, header=None, nrows=max_scan_rows)
    elif suffix in [".xlsx", ".xls"]:
        engine = "openpyxl" if suffix == ".xlsx" else "xlrd"
        df_raw = pd.read_excel(file_path, header=None, nrows=max_scan_rows, engine=engine)
    else:
        raise ValueError(f"不支持的文件格式: {suffix}")
    
    best_header_row = 0
    best_score = -1
    
    for i in range(min(max_scan_rows, len(df_raw))):
        row = df_raw.iloc[i]
        score = _calculate_header_score(row, df_raw, i)
        
        if score > best_score:
            best_score = score
            best_header_row = i
            
    return best_header_row
def _calculate_header_score(row: pd.Series, df_raw: pd.DataFrame, row_index: int) -> float:
    """
    计算某一行作为列头的得分
    """
    score = 0.0
    total_cols = len(row)
    
    if total_cols == 0:
        return -1
    
    # 1. 非空值比例（列头通常比较完整）
    non_null_ratio = row.notna().sum() / total_cols
    score += non_null_ratio * 30
    
    # 2. 字符串类型比例（列头通常是字符串）
    string_count = sum(1 for val in row if isinstance(val, str) and val.strip())
    string_ratio = string_count / total_cols
    score += string_ratio * 25
    
    # 3. 唯一值比例（列名应该唯一）
    non_null_values = row.dropna()
    if len(non_null_values) > 0:
        unique_ratio = len(non_null_values.unique()) / len(non_null_values)
        score += unique_ratio * 20
    
    # 4. 检查下一行是否有数值类型（数据行特征）
    if row_index + 1 < len(df_raw):
        next_row = df_raw.iloc[row_index + 1]
        numeric_count = sum(1 for val in next_row if _is_numeric(val))
        if numeric_count > 0:
            score += 15
    
    # 5. 检查是否包含常见的列头关键词
    header_keywords = ['id', 'name', '名称', '编号', '日期', 'date', 'time', '时间', 
                       '金额', 'amount', '数量', 'quantity', '备注', '说明', 'type', '类型']
    keyword_match = sum(1 for val in row if isinstance(val, str) and 
                        any(kw in val.lower() for kw in header_keywords))
    score += min(keyword_match * 5, 10)  # 最多加10分
    
    return score
def _is_numeric(val) -> bool:
    """判断值是否为数值类型"""
    if pd.isna(val):
        return False
    if isinstance(val, (int, float)):
        return True
    if isinstance(val, str):
        try:
            float(val.replace(',', ''))
            return True
        except:
            return False
    return False
def read_data_file(file_path: str | Path, header_row: Optional[int] = None, 
                   auto_detect_header: bool = True) -> pd.DataFrame:
    """
    读取单个数据文件，返回DataFrame
    
    Args:
        file_path: 数据文件路径
        header_row: 指定列头行（0-based），如果为None则自动检测
        auto_detect_header: 是否自动检测列头行位置
        
    Returns:
        DataFrame
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    suffix = file_path.suffix.lower()
    
    # 确定列头行
    if header_row is None and auto_detect_header:
        header_row = detect_header_row(file_path)
    elif header_row is None:
        header_row = 0
    
    # 读取文件
    if suffix == ".csv":
        return read_csv_with_encoding(file_path, header=header_row)
    elif suffix == ".xlsx":
        return pd.read_excel(file_path, header=header_row, engine="openpyxl")
    elif suffix == ".xls":
        return pd.read_excel(file_path, header=header_row, engine="xlrd")
    else:
        raise ValueError(f"不支持的文件格式: {suffix}")


def get_file_info(file_path: str | Path, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """
    提取文件信息，包括字段名、样本数据、数据行数等
    
    Args:
        file_path: 数据文件路径
        df: 可选的已读取的DataFrame，如果未提供则重新读取
        
    Returns:
        文件信息字典，包含：
        - file_path: 文件绝对路径
        - file_name: 文件名（不含扩展名）
        - columns: 字段名列表
        - sample_data: 样本数据（前N行）
        - total_rows: 总行数
        - total_columns: 总列数
    """
    file_path = Path(file_path)
    
    if df is None:
        df = read_data_file(file_path)
    
    # 获取样本数据并转换为字符串格式（便于展示给LLM）
    sample_df = df.head(7)
    sample_data = sample_df.to_dict(orient="records")
    
    # 将样本数据转为字符串表示
    sample_str = sample_df.to_string(index=False)
    
    return {
        "file_path": str(file_path.absolute()),
        "file_name": file_path.stem,
        "columns": list(df.columns),
        "sample_data": sample_data,
        "sample_str": sample_str,
        "total_rows": len(df),
        "total_columns": len(df.columns),
    }


def load_all_files(folder_path: str) -> List[Tuple[Path, pd.DataFrame, Dict[str, Any]]]:
    """
    加载文件夹中的所有数据文件
    
    Args:
        folder_path: 文件夹路径
        
    Returns:
        列表，每个元素为 (文件路径, DataFrame, 文件信息字典)
    """
    files = scan_data_files(folder_path)
    results = []
    
    for file_path in files:
        try:
            df = read_data_file(file_path)
            info = get_file_info(file_path, df)
            results.append((file_path, df, info))
            print(f"✓ 已加载: {file_path.name} ({info['total_rows']} 行, {info['total_columns']} 列)")
        except Exception as e:
            print(f"✗ 加载失败: {file_path.name} - {e}")
    
    return results


if __name__ == "__main__":
    # 测试代码
    import sys
    
    if len(sys.argv) > 1:
        folder = sys.argv[1]
        files = scan_data_files(folder)
        print(f"找到 {len(files)} 个数据文件:")
        for f in files:
            print(f"  - {f}")
    else:
        print("用法: python data_loader.py <文件夹路径>")

