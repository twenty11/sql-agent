"""
LangGraph 状态定义模块
使用 TypedDict 定义工作流状态
"""

from typing import Any, List, Optional
from typing_extensions import TypedDict, NotRequired


# ============== 表选择相关类型 ==============

class TableSelectionItem(TypedDict):
    """选中的表信息"""
    table_name: str           # 表名
    schema_content: str       # 表结构文档内容
    selection_reason: str     # 选择该表的理由


# ============== JOIN 规划相关类型 ==============

class JoinCondition(TypedDict):
    """JOIN 条件定义"""
    left_table: str           # 左表名
    right_table: str          # 右表名
    left_column: str          # 左表关联字段
    right_column: str         # 右表关联字段
    join_type: str            # JOIN 类型: INNER, LEFT, RIGHT
    join_reason: str          # JOIN 理由说明


class JoinPlan(TypedDict):
    """JOIN 规划"""
    is_multi_table: bool              # 是否多表查询
    join_conditions: List[JoinCondition]  # JOIN 条件列表
    join_order: List[str]             # 建议的 JOIN 顺序
    planning_notes: str               # 规划说明


class GraphState(TypedDict):
    """
    LangGraph 工作流状态定义

    Attributes:
        question: 用户的自然语言问题（可能被改写）
        original_question: 用户原始问题
        question_rewritten: 问题是否已被改写
        retrieved_schemas: 从向量库检索到的相关表结构列表
        generated_sql: LLM 生成的 SQL 查询语句
        sql_valid: SQL 语法检查是否通过
        sql_check_message: SQL 检查结果消息
        execution_result: SQL 执行结果
        execution_success: SQL 执行是否成功
        error_message: 错误信息（语法错误或执行错误）
        retry_count: 当前重试次数
        final_answer: 最终生成的自然语言答案
        log_context: 日志上下文对象（用于记录工作流执行信息）
        fused_question: 融合后的问题（供下游使用）
        question_type: 问题类型（standalone|continuation|ambiguous）
        fusion_confidence: 融合置信度 0.0~1.0
        fusion_reason: 融合理由说明
        intent_type: 意图类型（query|analysis|hybrid|clarify）
        available_results: 当前会话可引用的历史结果摘要
        referenced_results: 本次实际引用的历史结果快照
    """
    # 输入
    question: str
    original_question: Optional[str]
    question_rewritten: bool
    log_context: Optional[Any]  # 日志上下文对象

    # ── 问题融合阶段（新增）──────────────────────────────────────
    fused_question: str                    # 融合后的问题
    question_type: str                     # standalone | continuation | ambiguous
    fusion_confidence: float               # 置信度 0.0~1.0
    fusion_reason: str                     # 融合说明
    intent_type: str                       # query | analysis | hybrid | clarify
    referenced_result_ids: List[str]       # 本轮引用的历史查询结果 ID
    sql_question: str                      # hybrid 场景下用于查询缺失数据的问题
    clarification_message: str             # clarify 场景下给用户的澄清提示

    # 检索阶段
    retrieved_schemas: List[str]

    # 表选择阶段
    selected_tables: List[TableSelectionItem]   # 选中的表列表
    table_selection_reason: str                  # 整体选择理由

    # JOIN 规划阶段
    join_plan: Optional[JoinPlan]               # JOIN 规划（单表时为 None）


    # SQL 生成阶段
    generated_sql: str
    
    # SQL 检查阶段
    sql_valid: bool
    sql_check_message: str
    
    # 执行阶段
    execution_result: Optional[Any]
    execution_success: bool
    error_message: Optional[str]
    
    # 重试控制
    retry_count: int

    # 输出
    final_answer: str
    query_explanation: str  # 查询表说明
    analysis_context: str   # 分析分支的结构化上下文

    # ── 企业级扩展字段（可选，向后兼容）──────────────────────────
    user_id: NotRequired[Optional[str]]          # 当前用户 ID
    tenant_id: NotRequired[Optional[str]]        # 租户 ID（为未来多租户预留）
    session_id: NotRequired[Optional[str]]       # 会话 ID（LangGraph checkpointer 使用）
    allowed_tables: NotRequired[Optional[List[str]]]  # 权限白名单：None=不限制（admin）；list=白名单（空列表=拒绝所有）
    conversation_history: NotRequired[Optional[List[dict]]]  # 最近 N 轮对话历史
    group_table_filter: NotRequired[Optional[List[str]]]  # 用户选择分组后的表名列表（Milvus 元数据预过滤）
    available_results: NotRequired[List[dict]]       # 当前 session 最近查询结果摘要
    referenced_results: NotRequired[List[dict]]      # 本次分析实际加载的查询结果快照
