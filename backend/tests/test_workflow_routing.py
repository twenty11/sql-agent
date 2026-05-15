import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import graph.workflow as workflow


def test_main_workflow_clarify_intent_ends_before_retrieve(monkeypatch):
    def fake_context_fusion(_state):
        return {
            "intent_type": "clarify",
            "question_type": "ambiguous",
            "fusion_confidence": 0.9,
            "fusion_reason": "缺少查询条件",
            "fused_question": "分析一下",
            "referenced_result_ids": [],
            "sql_question": "",
            "clarification_message": "请补充要查询的公司、指标或期间。",
        }

    def fail_retrieve(_state):
        raise AssertionError("clarify intent should not reach retrieve")

    monkeypatch.setattr(workflow, "context_fusion_node", fake_context_fusion)
    monkeypatch.setattr(workflow, "retrieve_node", fail_retrieve)

    app = workflow.create_workflow_without_answer().compile()
    events = list(app.stream(workflow.get_initial_state("分析一下")))

    assert len(events) == 1
    assert "context_fusion" in events[0]
    assert events[0]["context_fusion"]["intent_type"] == "clarify"


def test_main_workflow_empty_success_ends_without_rewrite(monkeypatch):
    def fake_context_fusion(_state):
        return {
            "intent_type": "query",
            "question_type": "standalone",
            "fusion_confidence": 1.0,
            "fusion_reason": "查询问题",
            "fused_question": "查询不存在的数据",
            "referenced_result_ids": [],
            "sql_question": "查询不存在的数据",
            "clarification_message": "",
        }

    def fake_retrieve(_state):
        return {"retrieved_schemas": ["英文表名: table_a\n字段: id"]}

    def fake_table_selection(_state):
        return {
            "selected_tables": [{
                "table_name": "table_a",
                "schema_content": "英文表名: table_a\n字段: id",
            }],
            "table_selection_reason": "测试表",
        }

    def fake_generate_sql(_state):
        return {"generated_sql": "SELECT id FROM table_a WHERE id = -1", "retry_count": 1}

    def fake_check_query(_state):
        return {"sql_valid": True, "sql_check_message": "SQL 检查通过", "error_message": None}

    def fake_execute(_state):
        return {
            "execution_success": True,
            "execution_result": {"columns": ["id"], "rows": [], "row_count": 0},
            "error_message": None,
        }

    def fail_rewrite(_state):
        raise AssertionError("empty successful result should not reach rewrite_question")

    monkeypatch.setattr(workflow, "context_fusion_node", fake_context_fusion)
    monkeypatch.setattr(workflow, "retrieve_node", fake_retrieve)
    monkeypatch.setattr(workflow, "table_selection_node", fake_table_selection)
    monkeypatch.setattr(workflow, "generate_sql_node", fake_generate_sql)
    monkeypatch.setattr(workflow, "check_query_node", fake_check_query)
    monkeypatch.setattr(workflow, "execute_node", fake_execute)
    monkeypatch.setattr(workflow, "rewrite_question_node", fail_rewrite)

    app = workflow.create_workflow_without_answer().compile()
    events = list(app.stream(workflow.get_initial_state("查询不存在的数据")))

    assert any("execute" in event for event in events)
    assert not any("rewrite_question" in event for event in events)
