"""LangGraph 节点实现模块。

职责边界：
- 本模块实现各节点的“业务动作”（检索、规划、生成、检查、执行、回答）。
- 工作流图中的路由与重试策略在 ``graph.workflow``；此处只负责读写状态字段。

隐藏约束：
- 多数节点以 ``GraphState`` 的松散 dict 形式读写字段，字段名即契约。
- 若新增状态字段，需同步考虑：路由条件、日志埋点和流式输出回放。
"""

import re
import threading
from typing import Any, Dict, Generator, List, Tuple, Optional
import json

import sqlparse
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from sqlalchemy import text

from config import get_settings
from db.connection import get_engine
from vectorstore.milvus_store import MilvusStore, get_milvus_store
from .state import GraphState
from .prompts import (
    QUESTION_REWRITE_PROMPT,
    SQL_GENERATION_PROMPT,
    TABLE_SELECTION_PROMPT,
    JOIN_PLANNING_PROMPT,
    ANSWER_PROMPT,
    ANALYSIS_ANSWER_PROMPT,
    ERROR_ANSWER_PROMPT,
    QUERY_EXPLANATION_PROMPT,
    CONTEXT_FUSION_PROMPT,
)
from utils.workflow_logger import NodeLogger


# 全局变量，延迟初始化（使用锁保证多线程/ASGI worker 下只初始化一次）
_llm: Optional[ChatOpenAI] = None
_llm_lock = threading.Lock()

_vector_store_manager: Optional[MilvusStore] = None
_vector_store_lock = threading.Lock()


def get_llm(model: str = None) -> ChatOpenAI:
    """获取 LLM 实例（进程级单例，线程安全）。

    采用双重检查锁（DCL）：常态下无锁读，仅首次初始化加锁。

    Notes:
        该函数首次调用后会缓存实例；后续传入不同 ``model`` 参数不会重新初始化。
        因此如果需要多模型并存，应避免复用该单例入口。
    """
    global _llm
    if _llm is None:
        with _llm_lock:
            if _llm is None:
                settings = get_settings()
                _llm = ChatOpenAI(
                    base_url=settings.llm_base_url,
                    model=model or settings.llm_model_name,
                    api_key=settings.llm_api_key,
                    temperature=0,
                )
    return _llm


def get_vector_store() -> MilvusStore:
    """获取向量存储管理器实例（进程级单例，线程安全）。"""
    global _vector_store_manager
    if _vector_store_manager is None:
        with _vector_store_lock:
            if _vector_store_manager is None:
                _vector_store_manager = get_milvus_store()
    return _vector_store_manager


# ============== 上下文融合节点 ==============

def context_fusion_node(state: GraphState) -> Dict[str, Any]:
    """
    上下文融合节点：判断问题类型并融合历史上下文

    职责：
    1. 如果无历史对话，直接透传问题
    2. 如果有历史对话，调用 LLM 判断问题类型（standalone/continuation/ambiguous）
    3. 对于 continuation 类型，融合历史上下文生成完整问题
    4. 对于 ambiguous 类型，降级为原始问题并标记低置信度
    5. 对于 standalone 类型，直接透传原始问题

    Args:
        state: 当前工作流状态

    Returns:
        Dict: 更新后的状态字段
            - fused_question: 融合后的问题
            - question_type: 问题类型
            - fusion_confidence: 融合置信度
            - fusion_reason: 融合理由
    """
    question = state["question"]
    original_question = state.get("original_question") or question
    conversation_history = state.get("conversation_history")
    available_results = state.get("available_results") or []
    log_context = state.get("log_context")

    # 记录日志
    logger = NodeLogger(log_context, "context_fusion")

    # 无历史且无可引用结果时直接透传
    if (not conversation_history or len(conversation_history) == 0) and not available_results:
        print(f"[上下文融合节点] 无历史对话（conversation_history 类型={type(conversation_history)}, 长度={len(conversation_history) if conversation_history else 0}），直接透传问题: {question}")
        logger.record(
            question_type="standalone",
            fusion_confidence=1.0,
            fusion_reason="无历史对话",
            fused_question=question,
            intent_type="query",
        )
        return {
            "fused_question": question,
            "question_type": "standalone",
            "fusion_confidence": 1.0,
            "fusion_reason": "无历史对话，直接透传",
            "intent_type": "query",
            "referenced_result_ids": [],
            "sql_question": question,
        }

    # 有历史时调用 LLM 判断并融合
    llm = get_llm()
    chain = CONTEXT_FUSION_PROMPT | llm | StrOutputParser()

    result = chain.invoke({
        "question": question,
        "conversation_history": conversation_history or "无",
        "available_results": _format_available_results_for_prompt(available_results),
    })

    # 解析 LLM 输出
    fusion = _parse_context_fusion(result, question)
    question_type = fusion["question_type"]
    fusion_confidence = fusion["confidence"]
    fusion_reason = fusion["reasoning"]
    intent_type = fusion["intent_type"]
    fused_question = fusion["fused_question"]
    sql_question = fusion["sql_question"] or fused_question
    referenced_result_ids = _normalize_referenced_result_ids(
        fusion["referenced_result_ids"],
        available_results,
    )
    if intent_type in ("analysis", "hybrid") and not referenced_result_ids and available_results:
        referenced_result_ids = [available_results[0]["id"]]

    # 低置信度时降级为原始问题
    if fusion_confidence < 0.6:
        print(f"[上下文融合节点] 置信度 {fusion_confidence} < 0.6，降级为原始问题")
        fused_question = question
        question_type = "ambiguous"
        intent_type = "query"
        sql_question = question
        referenced_result_ids = []

    if intent_type == "hybrid":
        fused_question = sql_question or fused_question
    elif intent_type == "query":
        sql_question = sql_question or fused_question
    else:
        sql_question = ""

    print(f"[上下文融合节点] 问题类型: {question_type}, 意图: {intent_type}, 置信度: {fusion_confidence}")
    print(f"[上下文融合节点] 原始问题: {question}")
    print(f"[上下文融合节点] 融合后问题: {fused_question}")
    print(f"[上下文融合节点] SQL问题: {sql_question}")
    print(f"[上下文融合节点] 引用结果: {referenced_result_ids}")
    print(f"[上下文融合节点] 融合理由: {fusion_reason}")

    # 记录关键信息
    logger.record(
        original_question=question,
        fused_question=fused_question,
        question_type=question_type,
        intent_type=intent_type,
        fusion_confidence=fusion_confidence,
        fusion_reason=fusion_reason,
        referenced_result_ids=referenced_result_ids,
    )

    return {
        "fused_question": fused_question,
        "question_type": question_type,
        "fusion_confidence": fusion_confidence,
        "fusion_reason": fusion_reason,
        "intent_type": intent_type,
        "referenced_result_ids": referenced_result_ids,
        "sql_question": sql_question,
    }


def _parse_context_fusion(llm_output: str, fallback_question: str) -> Dict[str, Any]:
    """
    解析上下文融合节点的 LLM 输出

    期望的 LLM 输出格式:
    问题类型: <standalone|continuation|ambiguous>
    融合置信度: <0.0~1.0>
    融合理由: <一句话说明>
    融合后问题: <完整的、可独立执行的问题>

    Args:
        llm_output: LLM 输出文本
        fallback_question: 降级时使用的原始问题

    Returns:
        Dict: 标准化后的融合与路由字段
    """
    parsed = {
        "question_type": "standalone",
        "intent_type": "query",
        "confidence": 1.0,
        "reasoning": "",
        "fused_question": fallback_question,
        "sql_question": fallback_question,
        "referenced_result_ids": [],
    }

    text = llm_output.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()

    try:
        data = json.loads(text)
        question_type = str(data.get("question_type", parsed["question_type"])).lower()
        intent_type = str(data.get("intent_type", parsed["intent_type"])).lower()
        if question_type in ("standalone", "continuation", "ambiguous"):
            parsed["question_type"] = question_type
        if intent_type in ("query", "analysis", "hybrid"):
            parsed["intent_type"] = intent_type
        parsed["confidence"] = max(0.0, min(1.0, float(data.get("confidence", parsed["confidence"]))))
        parsed["reasoning"] = str(data.get("reasoning", data.get("fusion_reason", ""))).strip()
        parsed["fused_question"] = str(data.get("fused_question") or fallback_question).strip()
        parsed["sql_question"] = str(data.get("sql_question") or parsed["fused_question"]).strip()
        ids = data.get("referenced_result_ids") or []
        parsed["referenced_result_ids"] = [str(v) for v in ids if v]
        return parsed
    except Exception:
        pass

    lines = llm_output.strip().split('\n')

    for line in lines:
        line = line.strip()

        if '问题类型' in line and ':' in line:
            value = line.split(':', 1)[1].strip().lower()
            if value in ("standalone", "continuation", "ambiguous"):
                parsed["question_type"] = value

        elif '融合置信度' in line and ':' in line:
            try:
                value = float(line.split(':', 1)[1].strip())
                parsed["confidence"] = max(0.0, min(1.0, value))  # 限制在 0~1
            except ValueError:
                pass

        elif '融合理由' in line and ':' in line:
            parsed["reasoning"] = line.split(':', 1)[1].strip()

        elif '融合后问题' in line and ':' in line:
            parsed["fused_question"] = line.split(':', 1)[1].strip()
            parsed["sql_question"] = parsed["fused_question"]

    return parsed


def _format_available_results_for_prompt(available_results: List[dict]) -> str:
    """把历史结果摘要压缩成路由节点可读的文本。"""
    if not available_results:
        return "无"

    lines = []
    for index, item in enumerate(available_results, 1):
        columns = item.get("columns") or []
        lines.append(
            f"{index}. id={item.get('id')}\n"
            f"   时间={item.get('created_at')}\n"
            f"   问题={item.get('question')}\n"
            f"   摘要={item.get('summary')}\n"
            f"   行数={item.get('row_count')}，字段={', '.join(str(c) for c in columns[:8])}"
        )
    return "\n".join(lines)


def _normalize_referenced_result_ids(result_ids: List[str], available_results: List[dict]) -> List[str]:
    """只保留当前 session 预加载结果池中存在的 id。"""
    available_ids = {str(item.get("id")) for item in available_results if item.get("id")}
    normalized = []
    for result_id in result_ids:
        result_id = str(result_id)
        if result_id in available_ids and result_id not in normalized:
            normalized.append(result_id)
    return normalized


# ============== 问题改写节点 ==============

def rewrite_question_node(state: GraphState) -> Dict[str, Any]:
    """
    问题改写节点：使用 LLM 改写用户问题

    当检索结果为空或无法生成 SQL 时触发，
    尝试理解用户意图并改写问题以获得更好的检索结果

    Args:
        state: 当前工作流状态

    Returns:
        Dict: 更新后的状态字段
    """
    question = state["question"]
    original_question = state.get("original_question") or question
    log_context = state.get("log_context")

    # 记录日志
    logger = NodeLogger(log_context, "rewrite_question")

    llm = get_llm()
    chain = QUESTION_REWRITE_PROMPT | llm | StrOutputParser()

    rewritten_question = chain.invoke({"question": question})
    rewritten_question = rewritten_question.strip()

    print(f"[问题改写节点] 原问题: {question}")
    print(f"[问题改写节点] 改写后: {rewritten_question}")

    # 记录关键信息
    logger.record(
        original_question=question,
        rewritten_question=rewritten_question
    )

    return {
        "question": rewritten_question,
        "original_question": original_question,
        "question_rewritten": True,
        "retry_count": 0,  # 重置重试计数
    }


# ============== 检索节点 ==============

def retrieve_node(state: GraphState) -> Dict[str, Any]:
    """
    检索节点：根据用户问题检索相关的表结构

    从 Milvus 向量库中检索与问题最相关的 Top-K 表结构，
    将检索结果存入状态供后续 SQL 生成使用

    Args:
        state: 当前工作流状态

    Returns:
        Dict: 更新后的状态字段
    """
    fused_question = state.get("fused_question", state["question"])
    log_context = state.get("log_context")

    # 记录日志
    logger = NodeLogger(log_context, "retrieve")

    vector_store = get_vector_store()
    group_table_filter = state.get("group_table_filter")
    allowed_tables = state.get("allowed_tables")

    # 当用户选择了分组时，在 Milvus 层用元数据过滤，只在该分组的表中检索
    if group_table_filter is not None:
        if allowed_tables is not None:
            # 取分组表和权限白名单的交集，保证用户不能越权
            allowed_set = {t.lower() for t in allowed_tables}
            milvus_filter = [t for t in group_table_filter if t.lower() in allowed_set]
        else:
            milvus_filter = group_table_filter
        schemas = vector_store.search_schemas(fused_question, table_names_filter=milvus_filter)
        print(f"[检索节点] 问题: {fused_question}")
        print(f"[检索节点] 分组过滤（{len(milvus_filter)} 个候选表），检索到 {len(schemas)} 个相关表结构")
    else:
        schemas = vector_store.search_schemas(fused_question)
        print(f"[检索节点] 问题: {fused_question}")
        print(f"[检索节点] 检索到 {len(schemas)} 个相关表结构")
        # 权限过滤：allowed_tables 语义 —— None 表示 admin 无限制；list 表示白名单（空列表=拒绝所有）
        if allowed_tables is not None:
            from auth.rbac import filter_schemas_by_permission
            schemas = filter_schemas_by_permission(schemas, allowed_tables)
            print(f"[检索节点] 权限过滤后剩余 {len(schemas)} 个表结构（白名单大小={len(allowed_tables)}）")

    # 记录关键信息
    logger.record(
        retrieved_count=len(schemas),
        table_names=[s.split("\n")[0].replace("# ", "") for s in schemas[:5]]  # 提取表名
    )

    return {
        "retrieved_schemas": schemas,
        "retry_count": 0,  # 初始化重试计数
    }


# ============== 表选择节点 ==============

def table_selection_node(state: GraphState) -> Dict[str, Any]:
    """
    表选择节点：根据检索到的表结构，让 LLM 明确选择需要使用的表

    分析用户问题和检索到的表结构，选择真正需要的表，
    过滤掉不相关的表，减少后续 SQL 生成的干扰

    Args:
        state: 当前工作流状态

    Returns:
        Dict: 更新后的状态字段
            - selected_tables: 选中的表列表
            - table_selection_reason: 选择理由
    """
    fused_question = state.get("fused_question", state["question"])
    retrieved_schemas = state["retrieved_schemas"]
    log_context = state.get("log_context")

    # 记录日志
    logger = NodeLogger(log_context, "table_selection")

    if not retrieved_schemas:
        print("[表选择节点] 没有检索到表结构，跳过选择")
        logger.record(
            selected_count=0,
            selected_tables=[],
            selection_reason="没有检索到相关表结构"
        )
        return {
            "selected_tables": [],
            "table_selection_reason": "没有检索到相关表结构",
        }

    llm = get_llm()

    # 构建表结构上下文
    schemas_text = "\n\n---\n\n".join(
        f"[表 {i+1}]\n{schema}"
        for i, schema in enumerate(retrieved_schemas)
    )

    # 调用 LLM 进行表选择
    chain = TABLE_SELECTION_PROMPT | llm | StrOutputParser()

    result = chain.invoke({
        "fused_question": fused_question,
        "schemas": schemas_text,
        "table_count": len(retrieved_schemas),
    })

    # 解析 LLM 输出
    selected_tables, selection_reason = _parse_table_selection(result, retrieved_schemas)

    print(f"[表选择节点] 问题: {fused_question}")
    print(f"[表选择节点] 检索到 {len(retrieved_schemas)} 个表，选中 {len(selected_tables)} 个")
    print(f"[表选择节点] 选中的表: {[t['table_name'] for t in selected_tables]}")

    # 记录关键信息
    logger.record(
        selected_count=len(selected_tables),
        selected_tables=[t['table_name'] for t in selected_tables],
        selection_reason=selection_reason
    )

    return {
        "selected_tables": selected_tables,
        "table_selection_reason": selection_reason,
    }


def _parse_table_selection(
    llm_output: str,
    retrieved_schemas: List[str]
) -> Tuple[List[Dict], str]:
    """
    解析 LLM 的表选择输出

    期望的 LLM 输出格式:
    ```
    选中的表:
    1. table_name_1: 选择理由
    2. table_name_2: 选择理由

    整体说明: xxx
    ```

    Args:
        llm_output: LLM 输出文本
        retrieved_schemas: 原始检索到的表结构列表

    Returns:
        Tuple[List[Dict], str]: (选中的表列表, 整体选择理由)

    Why:
        LLM 输出是自然语言而非强结构化 JSON，这里采用“弱格式约定 + 失败兜底”策略：
        一旦解析不到任何合法表名，直接回退到“使用全部检索表”，避免流程中断。
    """
    selected_tables = []
    overall_reason = ""

    # 构建表名到 schema 的映射
    table_schema_map = {}
    for schema in retrieved_schemas:
        # 从 schema 文档中提取表名（格式: "英文表名: xxx"）
        match = re.search(r'英文表名:\s*(\w+)', schema)
        if match:
            table_schema_map[match.group(1)] = schema

    # 解析选中的表
    lines = llm_output.strip().split('\n')
    in_selection_section = False

    for line in lines:
        line = line.strip()

        if '选中的表' in line or '选择的表' in line:
            in_selection_section = True
            continue

        if '整体说明' in line or '总体说明' in line:
            in_selection_section = False
            # 提取整体说明
            if ':' in line or '：' in line:
                overall_reason = re.split(r'[:：]', line, 1)[1].strip()
            continue

        if in_selection_section and line:
            # 解析格式: "1. table_name: 理由" 或 "- table_name: 理由"
            match = re.match(r'^[\d\.\-\*]+\s*(\w+)\s*[:：]\s*(.+)$', line)
            if match:
                table_name = match.group(1)
                reason = match.group(2)

                if table_name in table_schema_map:
                    selected_tables.append({
                        "table_name": table_name,
                        "schema_content": table_schema_map[table_name],
                        "selection_reason": reason,
                    })

    # 如果解析失败，回退到使用所有检索到的表。
    # 该策略牺牲精确性换取可用性：宁可多表噪音，也不让 SQL 生成因空输入直接失败。
    if not selected_tables:
        print("[表选择节点] 警告: 解析失败，使用所有检索到的表")
        for table_name, schema in table_schema_map.items():
            selected_tables.append({
                "table_name": table_name,
                "schema_content": schema,
                "selection_reason": "自动选择",
            })
        overall_reason = "解析失败，自动选择所有检索到的表"

    return selected_tables, overall_reason


# ============== JOIN 规划节点 ==============

def join_planning_node(state: GraphState) -> Dict[str, Any]:
    """
    JOIN 规划节点：分析多表之间的关联关系，规划 JOIN 路径

    当选中多张表时，分析表之间的关联关系（主外键、业务逻辑关联），
    生成 JOIN 计划供 SQL 生成节点使用

    Args:
        state: 当前工作流状态

    Returns:
        Dict: 更新后的状态字段
            - join_plan: JOIN 规划
    """
    fused_question = state.get("fused_question", state["question"])
    selected_tables = state["selected_tables"]
    log_context = state.get("log_context")

    # 记录日志
    logger = NodeLogger(log_context, "join_planning")

    # 单表查询，不需要 JOIN 规划
    if len(selected_tables) <= 1:
        print("[JOIN规划节点] 单表查询，跳过 JOIN 规划")
        join_plan = {
            "is_multi_table": False,
            "join_conditions": [],
            "join_order": [selected_tables[0]["table_name"]] if selected_tables else [],
            "planning_notes": "单表查询，无需 JOIN",
        }
        logger.record(
            is_multi_table=False,
            join_conditions_count=0
        )
        return {"join_plan": join_plan}

    llm = get_llm()

    # 构建选中表的结构信息
    tables_info = "\n\n---\n\n".join(
        f"[表: {t['table_name']}]\n{t['schema_content']}"
        for t in selected_tables
    )

    table_names = [t["table_name"] for t in selected_tables]

    # 调用 LLM 进行 JOIN 规划
    chain = JOIN_PLANNING_PROMPT | llm | StrOutputParser()

    result = chain.invoke({
        "fused_question": fused_question,
        "tables_info": tables_info,
        "table_names": ", ".join(table_names),
    })

    # 解析 JOIN 规划
    join_plan = _parse_join_plan(result, table_names)

    print(f"[JOIN规划节点] 问题: {fused_question}")
    print(f"[JOIN规划节点] 涉及 {len(selected_tables)} 张表")
    print(f"[JOIN规划节点] JOIN 条件数: {len(join_plan['join_conditions'])}")

    # 记录关键信息
    logger.record(
        is_multi_table=True,
        join_conditions_count=len(join_plan['join_conditions']),
        join_order=join_plan['join_order']
    )

    return {
        "join_plan": join_plan,
    }


def _parse_join_plan(llm_output: str, table_names: List[str]) -> Dict:
    """
    解析 LLM 的 JOIN 规划输出

    期望的 LLM 输出格式:
    ```
    JOIN 规划:
    1. table_a LEFT JOIN table_b ON table_a.id = table_b.a_id
       理由: xxx
    2. ... JOIN ... ON ...
       理由: xxx

    JOIN 顺序: table_a -> table_b -> table_c

    规划说明: xxx
    ```

    Args:
        llm_output: LLM 输出文本
        table_names: 选中的表名列表

    Returns:
        Dict: JOIN 规划字典

    Notes:
        解析逻辑对 JOIN 条件采用正则抽取，可能丢失复杂表达式（如函数条件、复合条件）。
        当前设计目标是约束主干 JOIN 关系，而非完整复刻 LLM 原文。
    """
    join_conditions = []
    join_order = []
    planning_notes = ""

    lines = llm_output.strip().split('\n')
    current_join = None

    for line in lines:
        line = line.strip()

        # 解析 JOIN 条件
        # 格式: "table_a LEFT JOIN table_b ON table_a.col = table_b.col"
        join_match = re.search(
            r'(\w+)\s+(INNER|LEFT|RIGHT|FULL|CROSS)?\s*JOIN\s+(\w+)\s+ON\s+(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)',
            line,
            re.IGNORECASE
        )

        if join_match:
            left_table = join_match.group(1)
            join_type = (join_match.group(2) or "INNER").upper()
            right_table = join_match.group(3)
            left_ref_table = join_match.group(4)
            left_column = join_match.group(5)
            right_ref_table = join_match.group(6)
            right_column = join_match.group(7)

            current_join = {
                "left_table": left_table,
                "right_table": right_table,
                "left_column": left_column if left_ref_table == left_table else right_column,
                "right_column": right_column if right_ref_table == right_table else left_column,
                "join_type": join_type,
                "join_reason": "",
            }
            join_conditions.append(current_join)
            continue

        # 解析 JOIN 理由
        if current_join and ('理由' in line or 'reason' in line.lower()):
            if ':' in line or '：' in line:
                current_join["join_reason"] = re.split(r'[:：]', line, 1)[1].strip()
            continue

        # 解析 JOIN 顺序
        if 'JOIN 顺序' in line or '顺序' in line:
            # 提取表名序列
            order_match = re.findall(r'\b(' + '|'.join(table_names) + r')\b', line)
            if order_match:
                join_order = order_match
            continue

        # 解析规划说明
        if '规划说明' in line or '说明' in line:
            if ':' in line or '：' in line:
                planning_notes = re.split(r'[:：]', line, 1)[1].strip()

    # 如果没有解析到 JOIN 顺序，使用输入顺序作为保守默认值，
    # 保证后续 prompt 至少有确定性的关联顺序可用。
    if not join_order:
        join_order = table_names

    return {
        "is_multi_table": True,
        "join_conditions": join_conditions,
        "join_order": join_order,
        "planning_notes": planning_notes or "多表关联查询",
    }


# ============== SQL 生成节点 ==============

def generate_sql_node(state: GraphState) -> Dict[str, Any]:
    """
    SQL 生成节点：根据问题、选中的表和 JOIN 规划生成 SQL

    改造后的节点只能使用已选表和已规划的 JOIN，
    将 JOIN 计划作为约束传入 SQL 生成 prompt

    Args:
        state: 当前工作流状态

    Returns:
        Dict: 更新后的状态字段
    """
    fused_question = state.get("fused_question", state["question"])
    selected_tables = state.get("selected_tables", [])
    join_plan = state.get("join_plan")
    error_message = state.get("error_message")
    retry_count = state.get("retry_count", 0)
    log_context = state.get("log_context")

    # 记录日志
    logger = NodeLogger(log_context, "generate_sql")

    # 兼容旧流程：如果没有 selected_tables，使用 retrieved_schemas
    if not selected_tables:
        schemas = state.get("retrieved_schemas", [])
        schemas_text = "\n\n---\n\n".join(schemas)
        join_constraint = ""
    else:
        # 使用选中的表结构
        schemas_text = "\n\n---\n\n".join(
            f"[表: {t['table_name']}]\n{t['schema_content']}"
            for t in selected_tables
        )

        # 构建 JOIN 约束
        join_constraint = _build_join_constraint(join_plan)

    # 构建错误上下文（如果有的话）
    error_context = ""
    if error_message and retry_count > 0:
        error_context = f"""
## 之前的错误
上一次生成的 SQL 执行失败，错误信息如下，请修正：
{error_message}
"""
    print(f"[SQL生成节点] 问题: {fused_question}")

    # 调用 LLM 生成 SQL
    llm = get_llm()
    chain = SQL_GENERATION_PROMPT | llm | StrOutputParser()

    generated_sql = chain.invoke({
        "schemas": schemas_text,
        "fused_question": fused_question,
        "join_constraint": join_constraint,
        "error_context": error_context,
    })

    # 清理 SQL（去除可能的 markdown 代码块标记）
    generated_sql = _clean_sql(generated_sql)

    print(f"[SQL生成节点] 生成的 SQL:\n{generated_sql}")

    # 记录关键信息
    logger.record(
        retry_attempts=retry_count,
        final_retry_count=retry_count
    )

    return {
        "generated_sql": generated_sql,
        "retry_count": retry_count + 1,
    }


def _build_join_constraint(join_plan: Optional[Dict]) -> str:
    """
    根据 JOIN 规划构建约束文本

    Args:
        join_plan: JOIN 规划字典

    Returns:
        str: JOIN 约束文本

    Why:
        把规划结果显式注入 SQL prompt，可降低模型“重新发明 JOIN 关系”的概率，
        尤其在表结构相似或同名字段较多时，能减少误连表风险。
    """
    if not join_plan or not join_plan.get("is_multi_table"):
        return ""

    lines = ["\n## JOIN 约束（必须遵守）"]
    lines.append("你必须按照以下规划进行表关联，不得自行添加或修改 JOIN 条件：")
    lines.append("")

    join_conditions = join_plan.get("join_conditions", [])

    if join_conditions:
        lines.append("### 规划的 JOIN 条件:")
        for i, jc in enumerate(join_conditions, 1):
            lines.append(
                f"{i}. {jc['left_table']} {jc['join_type']} JOIN {jc['right_table']} "
                f"ON {jc['left_table']}.{jc['left_column']} = {jc['right_table']}.{jc['right_column']}"
            )
            if jc.get("join_reason"):
                lines.append(f"   理由: {jc['join_reason']}")
        lines.append("")

    join_order = join_plan.get("join_order", [])
    if join_order:
        lines.append(f"### 建议的 JOIN 顺序: {' -> '.join(join_order)}")
        lines.append("")

    notes = join_plan.get("planning_notes", "")
    if notes:
        lines.append(f"### 规划说明: {notes}")

    return "\n".join(lines)


def _clean_sql(sql: str) -> str:
    """清理 SQL 字符串，去除 markdown 代码块等噪音包装。

    仅做最小化清洗，不改写 SQL 内容，避免引入语义偏差。
    """
    sql = sql.strip()
    
    # 移除 markdown 代码块标记
    if sql.startswith("```sql"):
        sql = sql[6:]
    elif sql.startswith("```"):
        sql = sql[3:]
    
    if sql.endswith("```"):
        sql = sql[:-3]
    
    return sql.strip()


# ============== SQL 检查节点 ==============

# 危险操作关键字
DANGEROUS_KEYWORDS = [
    "DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE",
    "INSERT", "UPDATE", "GRANT", "REVOKE"
]


def check_query_node(state: GraphState) -> Dict[str, Any]:
    """
    SQL 检查节点：验证生成的 SQL

    检查内容：
    1. SQL 语法是否正确（使用 sqlparse）
    2. 是否包含危险操作（DDL/DML）
    3. 是否是无法生成 SQL 的情况

    Args:
        state: 当前工作流状态

    Returns:
        Dict: 更新后的状态字段

    Safety:
        - 这里做的是“防御性拒绝”，不是完整 SQL 审计。
        - 关键目标是保证只允许 SELECT，降低误写库风险。
    """
    sql = state["generated_sql"]
    log_context = state.get("log_context")

    # 记录日志
    logger = NodeLogger(log_context, "check_query")

    # 检查是否是"无法生成SQL"的情况
    if sql.startswith("-- 无法生成SQL"):
        logger.record(
            sql_valid=False,
            check_message=sql
        )
        return {
            "sql_valid": False,
            "sql_check_message": sql,
            "error_message": sql,
        }

    # 检查危险操作。先做关键词拦截可以在 SQL 解析前快速失败，
    # 对明显危险输入提供更可读的错误信息。
    sql_upper = sql.upper()
    for keyword in DANGEROUS_KEYWORDS:
        # 使用正则确保是完整单词匹配
        pattern = r'\b' + keyword + r'\b'
        if re.search(pattern, sql_upper):
            message = f"检测到危险操作: {keyword}，只允许 SELECT 查询"
            print(f"[SQL检查节点] {message}")
            logger.record(
                sql_valid=False,
                check_message=message
            )
            return {
                "sql_valid": False,
                "sql_check_message": message,
                "error_message": message,
            }

    # 使用 sqlparse 检查语法
    try:
        parsed = sqlparse.parse(sql)
        if not parsed or not parsed[0].tokens:
            message = "SQL 语法解析失败：空语句"
            logger.record(
                sql_valid=False,
                check_message=message
            )
            return {
                "sql_valid": False,
                "sql_check_message": message,
                "error_message": message,
            }

        # 检查是否是 SELECT 语句
        stmt_type = parsed[0].get_type()
        if stmt_type and stmt_type.upper() != "SELECT":
            message = f"只允许 SELECT 查询，当前语句类型: {stmt_type}"
            logger.record(
                sql_valid=False,
                check_message=message
            )
            return {
                "sql_valid": False,
                "sql_check_message": message,
                "error_message": message,
            }

    except Exception as e:
        message = f"SQL 语法检查异常: {str(e)}"
        logger.record(
            sql_valid=False,
            check_message=message
        )
        return {
            "sql_valid": False,
            "sql_check_message": message,
            "error_message": message,
        }

    print("[SQL检查节点] SQL 检查通过")
    logger.record(
        sql_valid=True,
        check_message="SQL 检查通过"
    )

    # AST 级权限校验：allowed_tables=None 跳过（admin）；否则必须在白名单内
    allowed_tables = state.get("allowed_tables")
    if allowed_tables is not None:
        from auth.rbac import extract_tables_from_sql
        referenced_tables = extract_tables_from_sql(sql)
        allowed_set = {t.lower() for t in allowed_tables}
        forbidden = [t for t in referenced_tables if t not in allowed_set]
        if forbidden:
            msg = f"权限不足：SQL 引用了无权访问的表 {forbidden}"
            print(f"[SQL检查节点] {msg}")
            return {
                "sql_valid": False,
                "sql_check_message": msg,
                "error_message": msg,
            }

    return {
        "sql_valid": True,
        "sql_check_message": "SQL 检查通过",
        "error_message": None,
    }


# ============== 执行节点 ==============

def execute_node(state: GraphState) -> Dict[str, Any]:
    """
    执行节点：在数据库中执行 SQL

    执行生成的 SQL 查询并捕获结果或错误

    Args:
        state: 当前工作流状态

    Returns:
        Dict: 更新后的状态字段

    Exception Handling:
        捕获所有执行异常并写入 ``error_message``，由上层路由统一决定是否重试。
    """
    sql = state["generated_sql"]
    log_context = state.get("log_context")

    # 记录日志
    logger = NodeLogger(log_context, "execute")

    try:
        import time
        start_time = time.time()

        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(sql))

            # 获取列名
            columns = list(result.keys())

            # 获取所有行数据
            rows = result.fetchall()

            execution_time_ms = int((time.time() - start_time) * 1000)

            # 构建结果字典
            execution_result = {
                "columns": columns,
                "rows": [list(row) for row in rows],
                "row_count": len(rows),
            }

            print(f"[执行节点] 执行成功，返回 {len(rows)} 行数据")

            # 记录关键信息
            logger.record(
                execution_success=True,
                row_count=len(rows),
                execution_time_ms=execution_time_ms
            )

            return {
                "execution_result": execution_result,
                "execution_success": True,
                "error_message": None,
            }

    except Exception as e:
        error_msg = f"SQL 执行错误: {str(e)}"
        print(f"[执行节点] {error_msg}")

        # 记录错误信息
        logger.record(
            execution_success=False,
            error_message=error_msg
        )

        return {
            "execution_result": None,
            "execution_success": False,
            "error_message": error_msg,
        }


def result_loader_node(state: GraphState) -> Dict[str, Any]:
    """加载分析分支引用的历史查询结果，并构造 LLM 分析上下文。"""
    session_id = state.get("session_id")
    available_results = state.get("available_results") or []
    referenced_result_ids = state.get("referenced_result_ids") or []
    allowed_tables = state.get("allowed_tables")
    intent_type = state.get("intent_type", "query")
    log_context = state.get("log_context")
    logger = NodeLogger(log_context, "load_results")

    if not referenced_result_ids and available_results:
        referenced_result_ids = [available_results[0]["id"]]

    loaded_results = []
    if session_id and referenced_result_ids:
        from db.crud.query_results import get_query_results_by_ids_sync
        loaded_results = get_query_results_by_ids_sync(session_id, referenced_result_ids)

    filtered_results = [
        item for item in loaded_results
        if _query_result_allowed(item, allowed_tables)
    ]
    denied_count = len(loaded_results) - len(filtered_results)

    analysis_context = _build_analysis_context(
        referenced_results=filtered_results,
        current_result=state.get("execution_result") if intent_type == "hybrid" else None,
        current_sql=state.get("generated_sql") if intent_type == "hybrid" else None,
    )

    print(f"[结果加载节点] 加载历史结果 {len(filtered_results)} 条，过滤 {denied_count} 条")
    logger.record(
        requested_result_ids=referenced_result_ids,
        loaded_count=len(filtered_results),
        denied_count=denied_count,
    )

    return {
        "referenced_result_ids": [item["id"] for item in filtered_results],
        "referenced_results": filtered_results,
        "analysis_context": analysis_context,
    }


def _query_result_allowed(result_item: dict, allowed_tables: Optional[List[str]]) -> bool:
    """对历史结果做当前权限白名单复核。"""
    if allowed_tables is None:
        return True
    referenced_tables = result_item.get("referenced_tables") or []
    if not referenced_tables:
        return True
    allowed_set = {table.lower() for table in allowed_tables}
    for table in referenced_tables:
        normalized = str(table).strip('"').lower().split(".")[-1]
        if normalized not in allowed_set:
            return False
    return True


def _build_analysis_context(
    referenced_results: List[dict],
    current_result: Optional[dict] = None,
    current_sql: Optional[str] = None,
) -> str:
    """构建分析提示词上下文，控制行数并附带基础统计。"""
    parts = []
    for index, item in enumerate(referenced_results, 1):
        result_data = item.get("result_data") or {}
        parts.append(_format_result_snapshot_for_analysis(
            title=f"历史结果 {index}",
            question=item.get("question") or "",
            summary=item.get("summary") or "",
            sql=item.get("sql") or "",
            result_data=result_data,
            result_id=item.get("id"),
            created_at=item.get("created_at"),
        ))

    if current_result:
        parts.append(_format_result_snapshot_for_analysis(
            title="本轮新查询结果",
            question="本轮混合分析补充查询",
            summary="本轮为补齐对比或分析所需的新数据而查询",
            sql=current_sql or "",
            result_data=current_result,
        ))

    if not parts:
        return "没有可用查询结果。"
    return "\n\n---\n\n".join(parts)


def _format_result_snapshot_for_analysis(
    title: str,
    question: str,
    summary: str,
    sql: str,
    result_data: dict,
    result_id: Optional[str] = None,
    created_at: Optional[str] = None,
) -> str:
    columns = result_data.get("columns") or []
    rows = result_data.get("rows") or []
    row_count = result_data.get("row_count", len(rows))
    lines = [f"## {title}"]
    if result_id:
        lines.append(f"- 结果ID: {result_id}")
    if created_at:
        lines.append(f"- 查询时间: {created_at}")
    if question:
        lines.append(f"- 原问题: {question}")
    if summary:
        lines.append(f"- 摘要: {summary}")
    lines.append(f"- 总行数: {row_count}")
    lines.append(f"- 字段: {', '.join(str(c) for c in columns) if columns else '无'}")
    if sql:
        lines.append(f"- SQL: {sql}")

    lines.append("")
    lines.append("### 前 50 行")
    lines.append(_format_rows_table(columns, rows, max_rows=50))

    stats = _numeric_column_stats(columns, rows)
    if stats:
        lines.append("")
        lines.append("### 数值列基础统计")
        for stat in stats:
            lines.append(
                f"- {stat['column']}: count={stat['count']}, "
                f"min={stat['min']}, max={stat['max']}, avg={stat['avg']}"
            )
    return "\n".join(lines)


def _format_rows_table(columns: List[Any], rows: List[list], max_rows: int = 50) -> str:
    if not columns:
        return "无字段"
    if not rows:
        return "无数据行"

    display_columns = [str(c) for c in columns[:20]]
    lines = [
        "| " + " | ".join(display_columns) + " |",
        "| " + " | ".join("---" for _ in display_columns) + " |",
    ]
    for row in rows[:max_rows]:
        cells = [str(value) if value is not None else "" for value in list(row)[:20]]
        if len(cells) < len(display_columns):
            cells.extend([""] * (len(display_columns) - len(cells)))
        lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |")
    if len(rows) > max_rows:
        lines.append(f"\n仅展示前 {max_rows} 行，剩余 {len(rows) - max_rows} 行未注入模型。")
    return "\n".join(lines)


def _numeric_column_stats(columns: List[Any], rows: List[list]) -> List[dict]:
    stats = []
    for col_index, column in enumerate(columns):
        values = []
        for row in rows:
            if col_index >= len(row):
                continue
            value = row[col_index]
            if isinstance(value, bool) or value is None:
                continue
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                continue
        if values:
            avg = sum(values) / len(values)
            stats.append({
                "column": str(column),
                "count": len(values),
                "min": round(min(values), 6),
                "max": round(max(values), 6),
                "avg": round(avg, 6),
            })
    return stats


def _format_result(result: Dict[str, Any]) -> str:
    """格式化查询结果为文本上下文。

    Notes:
        为控制回答提示词长度，展示行数上限固定为 1000。
    """
    if not result:
        return "查询结果为空"
    
    columns = result.get("columns", [])
    rows = result.get("rows", [])
    row_count = result.get("row_count", 0)
    
    if row_count == 0:
        return "查询结果为空（0 行数据）"
    
    # 构建表格形式的结果
    lines = [f"共 {row_count} 行数据"]
    lines.append("列名: " + ", ".join(columns))
    lines.append("-" * 40)
    
    # 限制显示行数
    max_display_rows = 1000
    for i, row in enumerate(rows[:max_display_rows]):
        row_str = " | ".join(str(v) for v in row)
        lines.append(f"{i+1}. {row_str}")
    
    if row_count > max_display_rows:
        lines.append(f"... 还有 {row_count - max_display_rows} 行未显示")
    
    return "\n".join(lines)


# ============== 流式回答生成 ==============

def generate_answer_stream(state: dict) -> Generator[str, None, None]:
    """
    流式生成答案
    
    逐字输出答案内容，适用于前端流式展示
    最后 yield 一个特殊标记字典表示查询说明
    
    Args:
        state: 当前工作流状态
        
    Yields:
        str: 答案的每个片段
        dict: 最后 yield {"__explanation__": "查询说明内容"}
    """
    fused_question = state.get("fused_question", state.get("question", ""))
    execution_success = state.get("execution_success", False)
    schemas = state.get("retrieved_schemas", [])
    intent_type = state.get("intent_type", "query")
    
    llm = get_llm()
    query_explanation = ""
    
    if intent_type == "analysis" or state.get("analysis_context"):
        question = state.get("question", fused_question)
        analysis_context = state.get("analysis_context") or _build_analysis_context(
            referenced_results=state.get("referenced_results") or [],
            current_result=state.get("execution_result") if intent_type == "hybrid" else None,
            current_sql=state.get("generated_sql") if intent_type == "hybrid" else None,
        )
        chain = ANALYSIS_ANSWER_PROMPT | llm
        for chunk in chain.stream({
            "question": question,
            "analysis_context": analysis_context,
        }):
            content = chunk.content if hasattr(chunk, 'content') else str(chunk)
            yield content

        referenced_count = len(state.get("referenced_results") or [])
        if intent_type == "hybrid":
            query_explanation = f"本次为混合分析：引用 {referenced_count} 条历史查询结果，并结合本轮新查询结果进行分析。"
        else:
            query_explanation = f"本次为数据分析：引用 {referenced_count} 条历史查询结果，未重新查询数据库。"

    elif execution_success:
        # 成功执行，流式生成答案
        sql = state.get("generated_sql", "")
        result = state.get("execution_result")
        result_str = _format_result(result)

        # 生成查询表说明
        if schemas:
            schemas_text = "\n\n---\n\n".join(schemas)
            explanation_chain = QUERY_EXPLANATION_PROMPT | llm | StrOutputParser()
            query_explanation = explanation_chain.invoke({
                "schemas": schemas_text,
                "sql": sql,
                "question": fused_question,
            })
        
        # 流式生成答案
        chain = ANSWER_PROMPT | llm
        
        for chunk in chain.stream({
            "sql": sql,
            "result": result_str,
            "question": fused_question,
        }):
            content = chunk.content if hasattr(chunk, 'content') else str(chunk)
            yield content
        
    else:
        # 执行失败，流式生成错误说明
        error = state.get("error_message", "未知错误")
        
        chain = ERROR_ANSWER_PROMPT | llm
        
        for chunk in chain.stream({
            "error": error,
            "question": fused_question,
        }):
            content = chunk.content if hasattr(chunk, 'content') else str(chunk)
            yield content
    
    print(f"[回答节点] 流式生成答案完成")

    # 最后 yield 查询说明
    yield {"__explanation__": query_explanation}



