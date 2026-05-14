"""
本地嵌入模型封装模块
使用 HuggingFace 本地模型 (如 bge-m3) 进行文本向量化
"""

from functools import lru_cache
from typing import List

from langchain_huggingface import HuggingFaceEmbeddings

from config import get_settings


@lru_cache()
def get_embeddings() -> HuggingFaceEmbeddings:
    """
    获取本地嵌入模型实例 (单例模式)
    
    使用 HuggingFace 的 sentence-transformers 加载本地模型
    默认使用 bge-m3 模型，支持中英文
    
    Returns:
        HuggingFaceEmbeddings: 嵌入模型实例
    """
    settings = get_settings()
    
    # 模型配置
    model_kwargs = {
        "device": "cpu",  # 可改为 "cuda" 使用 GPU
        "trust_remote_code": True,
    }
    
    # 编码配置
    encode_kwargs = {
        "normalize_embeddings": True,  # 归一化向量，便于余弦相似度计算
        "batch_size": 32,
    }
    
    embeddings = HuggingFaceEmbeddings(
        model_name=settings.embedding_model_path,
        model_kwargs=model_kwargs,
        encode_kwargs=encode_kwargs,
    )
    
    return embeddings


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    将文本列表转换为向量
    
    Args:
        texts: 文本列表
        
    Returns:
        List[List[float]]: 向量列表
    """
    embeddings = get_embeddings()
    return embeddings.embed_documents(texts)


def embed_query(query: str) -> List[float]:
    """
    将查询文本转换为向量
    
    Args:
        query: 查询文本
        
    Returns:
        List[float]: 查询向量
    """
    embeddings = get_embeddings()
    return embeddings.embed_query(query)
