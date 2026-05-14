"""LangGraph 工作流装配模块。

该模块负责把 ``graph.nodes`` 中的原子节点拼装成不同运行模式的图：

- SQL 评估图：用于离线评测 SQL 生成质量（可重试，不执行回答节点）。
- SQL 生成图：仅生成 SQL，不执行 SQL 与回答。
- 流式执行图：用于线上流式输出。

注意：本模块只定义"控制流"和"状态路由"，不承载业务推理细节。具体推理逻辑在
节点函数内部实现；这里重点维护的是重试策略、终止条件和分支切换时机。
"""

from typing import Callable, Generator

from langgraph.graph import StateGraph, END

from .state import GraphState
from .nodes import (
    retrieve_node,
    rewrite_question_node,
    table_selection_node,
    join_planning_node,
    generate_sql_node,
    check_query_node,
    execute_node,
    generate_answer_stream,
    context_fusion_node,
    result_loader_node,
)
from utils.workflow_logger import WorkflowLogger, LogContext
from config import get_settings


def save_graph_png(app=None) -> None:
    """保存工作流图为 graph_.png"""
    png_data = app.get_graph().draw_mermaid_png()
    with open("graph_.png", "wb") as f:
        f.write(png_data)
    print("[信息] 工作流图已保存到 graph_.png")


def get_initial_state(question: str, log_context=None) -> dict:
    """构建工作流初始状态。

    Args:
        question: 用户输入问题。
        log_context: 可选日志上下文，供节点记录埋点。

    Returns:
        dict: 可被 ``GraphState`` 接受的初始字段集合。
    """
    return {
        "question": question,
        "original_question": question,
        "question_rewritten": False,
        "log_context": log_context,
        # ── 问题融合阶段（新增）──────────────────────────────
        "fused_question": "",
        "question_type": "",
        "fusion_confidence": 1.0,
        "fusion_reason": "",
        "intent_type": "query",
        "referenced_result_ids": [],
        "sql_question": "",
        # 检索阶段
        "retrieved_schemas": [],
        # 表选择阶段
        "selected_tables": [],
        "table_selection_reason": "",
        # JOIN 规划阶段
        "join_plan": None,
        # SQL 生成阶段
        "generated_sql": "",
        "sql_valid": False,
        "sql_check_message": "",
        "execution_result": None,
        "execution_success": False,
        "error_message": None,
        "retry_count": 0,
        "final_answer": "",
        "query_explanation": "",
        "analysis_context": "",
        # 企业级扩展字段（可选）
        "user_id": None,
        "tenant_id": None,
        "session_id": None,
        "allowed_tables": None,
        "conversation_history": None,
        "group_table_filter": None,
        "available_results": [],
        "referenced_results": [],
    }


def create_workflow_without_answer() -> StateGraph:
    """创建纯执行编排图（不含回答节点）。

    创建不包含 answer 节点的工作流（用于流式输出）

    工作流在 execute 节点后结束，answer 由外部流式生成

    工作流:
    context_fusion → retrieve → table_selection → [条件路由] → join_planning → generate_sql → check_query → execute → END
                                                        ↓
                                                    (单表跳过)

    标题生成已移出主流程，由独立 HTTP 接口在第一轮 Q&A 完成后异步生成。

    Returns:
        StateGraph: 已装配但尚未 compile 的工作流。

    Why:
        将回答生成留在图外可以避免把流式 token 生产逻辑塞入节点，
        让图结构只处理"检索/生成/校验/执行"四类状态转换。
    """
    workflow = StateGraph(GraphState)

    # 添加节点
    workflow.add_node("context_fusion", context_fusion_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("table_selection", table_selection_node)
    workflow.add_node("join_planning", join_planning_node)
    workflow.add_node("generate_sql", generate_sql_node)
    workflow.add_node("check_query", check_query_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("rewrite_question", rewrite_question_node)
    workflow.add_node("load_results", result_loader_node)

    # 设置入口点
    workflow.set_entry_point("context_fusion")

    # context_fusion → 条件路由：纯分析跳过 SQL，查询/混合进入原 SQL 子图
    def route_after_context_fusion(state):
        """根据入口意图决定是否需要查询数据库。"""
        intent_type = state.get("intent_type", "query")
        if intent_type == "analysis":
            return "load_results"
        return "retrieve"

    workflow.add_conditional_edges(
        "context_fusion",
        route_after_context_fusion,
        {
            "load_results": "load_results",
            "retrieve": "retrieve",
        }
    )
    workflow.add_edge("retrieve", "table_selection")
    workflow.add_edge("load_results", END)

    # table_selection → 条件路由（多表 → join_planning，单表 → generate_sql）
    def route_after_table_selection(state):
        """按表数量路由。

        多表问题需要先做 JOIN 规划，单表问题直接进入 SQL 生成，
        以减少不必要的 LLM 推理步骤和提示词噪音。
        """
        selected_tables = state.get("selected_tables", [])
        if len(selected_tables) > 1:
            return "join_planning"
        return "generate_sql"

    workflow.add_conditional_edges(
        "table_selection",
        route_after_table_selection,
        {
            "join_planning": "join_planning",
            "generate_sql": "generate_sql",
        }
    )

    # join_planning → generate_sql
    workflow.add_edge("join_planning", "generate_sql")

    # generate_sql → check_query
    workflow.add_edge("generate_sql", "check_query")

    # 检查后的路由（不再路由到 answer，而是结束）
    def check_route_no_answer(state):
        """根据 SQL 检查结果决定后续动作。
 
        路由优先级：
        1) SQL 合法 -> 执行；
        2) 明确"无法生成SQL" -> 优先尝试一次改写问题；
        3) 其余失败 -> 在重试预算内回到 SQL 生成；
        4) 超过上限 -> 结束。
        """
        from config import get_settings
        settings = get_settings()
        max_retry = settings.max_retry_count

        sql_valid = state.get("sql_valid", False)
        retry_count = state.get("retry_count", 0)
        sql_check_message = state.get("sql_check_message", "")
        question_rewritten = state.get("question_rewritten", False)

        if sql_valid:
            return "execute"
        # 该分支通常代表语义层面失败，继续重试同一问题价值较低，
        # 因此优先触发"问题改写"提高检索命中概率。
        if "无法生成SQL" in sql_check_message:
            if not question_rewritten:
                return "rewrite_question"
            return END
        if retry_count < max_retry:
            return "generate_sql"
        return END

    workflow.add_conditional_edges(
        "check_query",
        check_route_no_answer,
        {
            "generate_sql": "generate_sql",
            "execute": "execute",
            "rewrite_question": "rewrite_question",
            END: END,
        }
    )

    # 执行后的路由
    def execute_route_no_answer(state):
        """根据 SQL 执行结果决定重试、改写或结束。

        约束：空结果仅允许触发一次改写，避免"天然空结果"场景进入循环。
        """
        from config import get_settings
        settings = get_settings()
        max_retry = settings.max_retry_count

        execution_success = state.get("execution_success", False)
        retry_count = state.get("retry_count", 0)
        question_rewritten = state.get("question_rewritten", False)
        execution_result = state.get("execution_result")

        if execution_success:
            row_count = execution_result.get("row_count", 0) if execution_result else 0
            # 对"有 SQL 但无数据"的场景做一次语义纠偏：
            # 可能是用户问题表述不完整导致过滤条件过窄。
            if row_count == 0 and not question_rewritten:
                return "rewrite_question"
            if state.get("intent_type") == "hybrid":
                return "load_results"
            return END  # 结束，后续由外部流式生成答案
        if retry_count < max_retry:
            return "generate_sql"
        return END

    workflow.add_conditional_edges(
        "execute",
        execute_route_no_answer,
        {
            "generate_sql": "generate_sql",
            "rewrite_question": "rewrite_question",
            "load_results": "load_results",
            END: END,
        }
    )

    workflow.add_edge("rewrite_question", "retrieve")

    return workflow


def create_sql_evaluation_workflow() -> StateGraph:
    """
    创建用于 SQL 评估的工作流（包含校验和重试）

    工作流在 check_query 节点后结束，包含重试机制

    工作流:
    context_fusion → retrieve → table_selection → [条件路由] → join_planning → generate_sql → check_query → [条件路由] → END
                                      ↓                                                    ↓
                                  (单表跳过)                                          (重试或结束)
    """
    workflow = StateGraph(GraphState)

    # 添加节点
    workflow.add_node("context_fusion", context_fusion_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("table_selection", table_selection_node)
    workflow.add_node("join_planning", join_planning_node)
    workflow.add_node("generate_sql", generate_sql_node)
    workflow.add_node("check_query", check_query_node)

    # 设置入口点
    workflow.set_entry_point("context_fusion")

    # context_fusion → retrieve
    workflow.add_edge("context_fusion", "retrieve")

    # retrieve → table_selection
    workflow.add_edge("retrieve", "table_selection")

    # table_selection → 条件路由（多表 → join_planning，单表 → generate_sql）
    def route_after_table_selection(state):
        """评估模式下沿用与线上一致的单/多表路由规则。"""
        selected_tables = state.get("selected_tables", [])
        if len(selected_tables) > 1:
            return "join_planning"
        return "generate_sql"

    workflow.add_conditional_edges(
        "table_selection",
        route_after_table_selection,
        {
            "join_planning": "join_planning",
            "generate_sql": "generate_sql",
        }
    )

    # join_planning → generate_sql
    workflow.add_edge("join_planning", "generate_sql")

    # generate_sql → check_query
    workflow.add_edge("generate_sql", "check_query")

    # check_query 后的路由（支持重试）
    def check_route_evaluation(state):
        """评估模式下仅关注 SQL 是否可校验通过。"""
        max_retry = 3  # 固定为 3 次重试

        sql_valid = state.get("sql_valid", False)
        retry_count = state.get("retry_count", 0)

        if sql_valid:
            return END
        if retry_count < max_retry:
            return "generate_sql"
        return END

    workflow.add_conditional_edges(
        "check_query",
        check_route_evaluation,
        {
            "generate_sql": "generate_sql",
            END: END,
        }
    )

    return workflow


def create_sql_generation_workflow() -> StateGraph:
    """
    创建仅用于 SQL 生成的工作流（用于评估）

    工作流在 generate_sql 节点后结束，不执行查询

    工作流:
    context_fusion → retrieve → table_selection → [条件路由] → join_planning → generate_sql → END
                                      ↓
                                  (单表跳过)
    """
    workflow = StateGraph(GraphState)

    # 添加节点
    workflow.add_node("context_fusion", context_fusion_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("table_selection", table_selection_node)
    workflow.add_node("join_planning", join_planning_node)
    workflow.add_node("generate_sql", generate_sql_node)
    workflow.add_node("rewrite_question", rewrite_question_node)

    # 设置入口点
    workflow.set_entry_point("context_fusion")

    # context_fusion → retrieve
    workflow.add_edge("context_fusion", "retrieve")

    # retrieve → table_selection
    workflow.add_edge("retrieve", "table_selection")

    # table_selection → 条件路由（多表 → join_planning，单表 → generate_sql）
    def route_after_table_selection(state):
        """SQL-only 模式复用单/多表分流，保证提示上下文一致。"""
        selected_tables = state.get("selected_tables", [])
        if len(selected_tables) > 1:
            return "join_planning"
        return "generate_sql"

    workflow.add_conditional_edges(
        "table_selection",
        route_after_table_selection,
        {
            "join_planning": "join_planning",
            "generate_sql": "generate_sql",
        }
    )

    # join_planning → generate_sql
    workflow.add_edge("join_planning", "generate_sql")

    # generate_sql 后结束（不检查、不执行）
    workflow.add_edge("generate_sql", END)

    workflow.add_edge("rewrite_question", "retrieve")

    return workflow


def run_sql_evaluation_with_retry(question: str) -> dict:
    """
    运行 SQL 评估工作流（包含校验和重试）

    生成 SQL 后进行校验，如果校验失败则重试，最多重试 3 次

    Args:
        question: 用户的自然语言问题

    Returns:
        dict: 包含以下字段
            - question: 用户的原始问题
            - generated_sql: 生成的 SQL 语句
            - selected_tables: 选中的表列表
            - join_plan: JOIN 规划信息（如果有多表）
            - retrieved_schemas: 检索到的表结构
            - table_selection_reason: 表选择的原因
            - sql_valid: SQL 是否通过校验
            - sql_check_message: SQL 校验信息
            - error: 错误信息（如果有）
    """
    settings = get_settings()

    # 初始化日志系统
    if settings.log_enabled:
        WorkflowLogger.initialize(settings)

    # 创建日志上下文
    log_context = LogContext("evaluation", question) if settings.log_enabled else None

    workflow = create_sql_evaluation_workflow()
    app = workflow.compile()

    # 初始化状态
    initial_state = get_initial_state(question, log_context)

    print("=" * 50)
    print(f"[SQL 评估] 开始处理问题: {question}")
    print("=" * 50)

    # 运行工作流
    current_state = initial_state.copy()

    try:
        for output in app.stream(initial_state):
            for node_name, node_output in output.items():
                current_state.update(node_output)
                print(f"[SQL 评估] 完成节点: {node_name}")
                if node_name == "check_query":
                    retry_count = current_state.get("retry_count", 0)
                    sql_valid = current_state.get("sql_valid", False)
                    print(f"[SQL 评估] 校验结果: 有效={sql_valid}, 重试次数={retry_count}")

        print("=" * 50)
        print("[SQL 评估] 处理完成")
        print("=" * 50)

        # 写入日志
        if log_context:
            log_context.finalize(current_state)
            WorkflowLogger.write_log(log_context, settings.log_format)

        return {
            "question": question,
            "generated_sql": current_state.get("generated_sql", ""),
            "selected_tables": current_state.get("selected_tables", []),
            "join_plan": current_state.get("join_plan"),
            "retrieved_schemas": current_state.get("retrieved_schemas", []),
            "table_selection_reason": current_state.get("table_selection_reason", ""),
            "sql_valid": current_state.get("sql_valid", False),
            "sql_check_message": current_state.get("sql_check_message", ""),
            "error": None,
        }
    except Exception as e:
        print(f"[SQL 评估] 错误: {str(e)}")

        # 写入错误日志
        if log_context:
            log_context.finalize(current_state)
            WorkflowLogger.write_log(log_context, settings.log_format)

        return {
            "question": question,
            "generated_sql": "",
            "selected_tables": [],
            "join_plan": None,
            "retrieved_schemas": [],
            "table_selection_reason": "",
            "sql_valid": False,
            "sql_check_message": "",
            "error": str(e),
        }


def run_sql_generation_only(question: str) -> dict:
    """
    仅运行 SQL 生成工作流（用于评估）

    只运行到 SQL 生成步骤，不执行查询，返回问题和生成的 SQL

    Args:
        question: 用户的自然语言问题

    Returns:
        dict: 包含以下字段
            - question: 用户的原始问题
            - generated_sql: 生成的 SQL 语句
            - selected_tables: 选中的表列表
            - join_plan: JOIN 规划信息（如果有多表）
            - retrieved_schemas: 检索到的表结构
            - error: 错误信息（如果有）
    """
    workflow = create_sql_generation_workflow()
    app = workflow.compile()

    # 初始化状态
    initial_state = get_initial_state(question)

    print("=" * 50)
    print(f"[SQL 评估] 开始处理问题: {question}")
    print("=" * 50)

    # 运行工作流到 generate_sql 完成
    current_state = initial_state.copy()

    try:
        for output in app.stream(initial_state):
            for node_name, node_output in output.items():
                current_state.update(node_output)
                print(f"[SQL 评估] 完成节点: {node_name}")

        print("=" * 50)
        print("[SQL 评估] 处理完成")
        print("=" * 50)

        return {
            "question": question,
            "generated_sql": current_state.get("generated_sql", ""),
            "selected_tables": current_state.get("selected_tables", []),
            "join_plan": current_state.get("join_plan"),
            "retrieved_schemas": current_state.get("retrieved_schemas", []),
            "table_selection_reason": current_state.get("table_selection_reason", ""),
            "error": None,
        }
    except Exception as e:
        print(f"[SQL 评估] 错误: {str(e)}")
        return {
            "question": question,
            "generated_sql": "",
            "selected_tables": [],
            "join_plan": None,
            "retrieved_schemas": [],
            "table_selection_reason": "",
            "error": str(e),
        }


def _run_workflow_branch(question: str, log_context=None) -> tuple[dict, list]:
    """执行工作流并收集节点事件。

    Returns:
        tuple[dict, list]:
            - 最终状态快照；
            - 节点事件列表 ``[(node_name, node_output), ...]``，供 SSE 状态回放。
    """
    workflow = create_workflow_without_answer()
    app = workflow.compile()
    

    initial_state = get_initial_state(question, log_context)

    current_state = initial_state.copy()
    node_events = []
    for output in app.stream(initial_state):
        for node_name, node_output in output.items():
            current_state.update(node_output)
            node_events.append((node_name, node_output))
    return current_state, node_events


def run_workflow(question: str) -> dict:
    """非流式入口：执行工作流 + 汇总完整回答。

    Notes:
        该函数会在图执行结束后再调用回答生成器，因此返回时 ``final_answer``
        总是完整字符串，适合同步 HTTP 接口。
    """
    settings = get_settings()
    if settings.log_enabled:
        WorkflowLogger.initialize(settings)
    log_context = LogContext("normal", question) if settings.log_enabled else None

    state, _ = _run_workflow_branch(question, log_context=log_context)

    answer = ""
    query_explanation = ""
    for chunk in generate_answer_stream(state):
        if isinstance(chunk, dict) and "__explanation__" in chunk:
            query_explanation = chunk["__explanation__"]
        else:
            answer += chunk
    state["final_answer"] = answer
    state["query_explanation"] = query_explanation

    if log_context and settings.log_enabled:
        log_context.finalize(state)
        WorkflowLogger.write_log(log_context, settings.log_format)
    return state


def run_workflow_stream(question: str, log_context=None) -> Generator[dict, None, None]:
    """流式入口：工作流执行后逐步产出事件。

    Yields:
        dict: 事件流对象，``type`` 可能为 ``status/answer_chunk/done`` 等。
    """
    settings = get_settings()

    state, node_events = _run_workflow_branch(question, log_context=log_context)

    yield {"type": "status", "content": "已按工作流执行"}

    for node_name, node_output in node_events:
        if node_name == "context_fusion":
            yield _intent_event(state)
        elif node_name == "load_results":
            count = len(node_output.get("referenced_results", []))
            yield {"type": "status", "content": f"已加载 {count} 条历史查询结果用于分析"}
        elif node_name == "retrieve":
            cnt = len(node_output.get("retrieved_schemas", []))
            yield {"type": "status", "content": f"检索到 {cnt} 个相关表结构"}
        elif node_name == "table_selection":
            names = [t.get("table_name") for t in node_output.get("selected_tables", [])]
            yield {"type": "status", "content": f"选中 {len(names)} 个表: {', '.join(names)}"}
        elif node_name == "join_planning":
            jc = len(node_output.get("join_plan", {}).get("join_conditions", []))
            yield {"type": "status", "content": f"完成 JOIN 规划，条件 {jc} 条"}
        elif node_name == "generate_sql":
            yield {"type": "status", "content": "正在生成 SQL 查询..."}
        elif node_name == "check_query" and node_output.get("sql_valid"):
            yield {"type": "status", "content": "SQL 检查通过"}
        elif node_name == "execute" and node_output.get("execution_success"):
            rc = node_output.get("execution_result", {}).get("row_count", 0)
            yield {"type": "status", "content": f"SQL 执行成功，返回 {rc} 行"}

    yield {"type": "status", "content": "正在生成答案..."}
    full_answer = ""
    query_explanation = ""
    for chunk in generate_answer_stream(state):
        if isinstance(chunk, dict) and "__explanation__" in chunk:
            query_explanation = chunk["__explanation__"]
        else:
            full_answer += chunk
            yield {"type": "answer_chunk", "content": chunk}
    state["final_answer"] = full_answer
    state["query_explanation"] = query_explanation
    if query_explanation:
        yield {"type": "explanation", "content": query_explanation}

    if log_context and settings.log_enabled:
        log_context.finalize(state)
        WorkflowLogger.write_log(log_context, settings.log_format)

    yield {"type": "done", "state": state}


def _cancelled(should_cancel: Callable[[], bool] | None) -> bool:
    return bool(should_cancel and should_cancel())


def _status_for_node(node_name: str, node_output: dict) -> dict | None:
    if node_name == "load_results":
        count = len(node_output.get("referenced_results", []))
        return {"type": "status", "content": f"已加载 {count} 条历史查询结果用于分析"}
    if node_name == "retrieve":
        cnt = len(node_output.get("retrieved_schemas", []))
        return {"type": "status", "content": f"检索到 {cnt} 个相关表结构"}
    if node_name == "table_selection":
        names = [t.get("table_name") for t in node_output.get("selected_tables", [])]
        return {"type": "status", "content": f"选中 {len(names)} 个表: {', '.join(names)}"}
    if node_name == "join_planning":
        jc = len(node_output.get("join_plan", {}).get("join_conditions", []))
        return {"type": "status", "content": f"完成 JOIN 规划，条件 {jc} 条"}
    if node_name == "generate_sql":
        return {"type": "status", "content": "正在生成 SQL 查询..."}
    if node_name == "check_query" and node_output.get("sql_valid"):
        return {"type": "status", "content": "SQL 检查通过"}
    if node_name == "execute" and node_output.get("execution_success"):
        rc = node_output.get("execution_result", {}).get("row_count", 0)
        return {"type": "status", "content": f"SQL 执行成功，返回 {rc} 行"}
    return None


def _intent_event(state: dict) -> dict:
    referenced_ids = set(state.get("referenced_result_ids") or [])
    available_results = state.get("available_results") or []
    referenced_results = [
        {
            "id": item.get("id"),
            "question": item.get("question"),
            "summary": item.get("summary"),
            "row_count": item.get("row_count"),
            "created_at": item.get("created_at"),
        }
        for item in available_results
        if item.get("id") in referenced_ids
    ]
    return {
        "type": "intent",
        "intent_type": state.get("intent_type", "query"),
        "referenced_results": referenced_results,
        "confidence": state.get("fusion_confidence", 1.0),
        "reason": state.get("fusion_reason", ""),
    }


def _mark_cancelled(state: dict, full_answer: str = "", query_explanation: str = "") -> dict:
    state["final_answer"] = full_answer
    state["query_explanation"] = query_explanation
    state["cancelled"] = True
    return state


def run_workflow_stream_with_session(
    question: str,
    session_id: str,
    user_id: str,
    allowed_tables: list[str],
    log_context=None,
    conversation_history: str | None = None,
    group_table_filter: list[str] | None = None,
    available_results: list[dict] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> Generator[dict, None, None]:
    """带会话和权限的流式入口（企业级版本）。

    与 run_workflow_stream 的区别：
    - 在 initial_state 中注入 user_id / session_id / allowed_tables
    - 权限过滤在 retrieve_node 和 check_query_node 内自动生效
    - 支持 conversation_history 参数注入历史对话上下文
    - 支持 group_table_filter 参数注入分组表名列表（Milvus 元数据预过滤）
    """
    settings = get_settings()

    initial = get_initial_state(question, log_context)
    initial["user_id"] = user_id
    initial["session_id"] = session_id
    initial["allowed_tables"] = allowed_tables  # None=不限制，list=白名单（空列表=拒绝所有）
    if conversation_history:
        initial["conversation_history"] = conversation_history
    if group_table_filter is not None:
        initial["group_table_filter"] = group_table_filter
    if available_results is not None:
        initial["available_results"] = available_results

    workflow = create_workflow_without_answer()
    app = workflow.compile()
    current_state = initial.copy()

    yield {"type": "status", "content": "已按工作流执行"}
    if _cancelled(should_cancel):
        yield {"type": "stopped", "state": _mark_cancelled(current_state)}
        return

    for output in app.stream(initial):
        for node_name, node_output in output.items():
            current_state.update(node_output)
            if node_name == "context_fusion":
                yield _intent_event(current_state)
            status_event = _status_for_node(node_name, node_output)
            if status_event:
                yield status_event
            if _cancelled(should_cancel):
                yield {"type": "stopped", "state": _mark_cancelled(current_state)}
                return

    if _cancelled(should_cancel):
        yield {"type": "stopped", "state": _mark_cancelled(current_state)}
        return

    yield {"type": "status", "content": "正在生成答案..."}
    full_answer = ""
    query_explanation = ""
    for chunk in generate_answer_stream(current_state):
        if _cancelled(should_cancel):
            yield {"type": "stopped", "state": _mark_cancelled(current_state, full_answer, query_explanation)}
            return
        if isinstance(chunk, dict) and "__explanation__" in chunk:
            query_explanation = chunk["__explanation__"]
        else:
            full_answer += chunk
            yield {"type": "answer_chunk", "content": chunk}
        if _cancelled(should_cancel):
            yield {"type": "stopped", "state": _mark_cancelled(current_state, full_answer, query_explanation)}
            return
    current_state["final_answer"] = full_answer
    current_state["query_explanation"] = query_explanation
    if query_explanation:
        yield {"type": "explanation", "content": query_explanation}

    if log_context and settings.log_enabled:
        log_context.finalize(current_state)
        WorkflowLogger.write_log(log_context, settings.log_format)

    yield {"type": "done", "state": current_state}
