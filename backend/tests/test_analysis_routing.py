import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import graph.nodes as nodes
from db.crud.query_results import build_query_result_summary
from graph.nodes import (
    _build_analysis_context,
    _normalize_referenced_result_ids,
    _parse_context_fusion,
    _query_result_allowed,
    context_fusion_node,
    generate_answer_stream,
    rewrite_question_node,
)
from graph.prompts import CONTEXT_FUSION_PROMPT


def test_context_fusion_prompt_only_requires_expected_variables():
    assert set(CONTEXT_FUSION_PROMPT.input_variables) == {
        "available_results",
        "conversation_history",
        "question",
    }


def test_parse_context_fusion_json_analysis():
    payload = {
        "question_type": "continuation",
        "intent_type": "analysis",
        "confidence": 0.92,
        "reasoning": "用户引用刚才的数据并要求分析",
        "fused_question": "分析刚才查询到的指标数据",
        "sql_question": "",
        "referenced_result_ids": ["r1"],
    }

    parsed = _parse_context_fusion(json.dumps(payload, ensure_ascii=False), "分析一下")

    assert parsed["question_type"] == "continuation"
    assert parsed["intent_type"] == "analysis"
    assert parsed["confidence"] == 0.92
    assert parsed["referenced_result_ids"] == ["r1"]


def test_parse_context_fusion_json_hybrid():
    payload = {
        "question_type": "continuation",
        "intent_type": "hybrid",
        "confidence": 0.86,
        "reasoning": "用户引用历史结果并新增公司",
        "fused_question": "比较刚才 A 公司与 B 公司指标",
        "sql_question": "查询 B 公司同一指标",
        "referenced_result_ids": ["r-old"],
    }

    parsed = _parse_context_fusion(json.dumps(payload, ensure_ascii=False), "和B公司比呢")

    assert parsed["intent_type"] == "hybrid"
    assert parsed["sql_question"] == "查询 B 公司同一指标"


def test_parse_context_fusion_json_clarify():
    payload = {
        "question_type": "ambiguous",
        "intent_type": "clarify",
        "confidence": 0.45,
        "reasoning": "用户没有说明要分析哪次结果",
        "fused_question": "分析一下",
        "sql_question": "",
        "referenced_result_ids": [],
        "clarification_message": "请说明要分析哪一次查询结果。",
    }

    parsed = _parse_context_fusion(json.dumps(payload, ensure_ascii=False), "分析一下")

    assert parsed["intent_type"] == "clarify"
    assert parsed["clarification_message"] == "请说明要分析哪一次查询结果。"


def test_normalize_referenced_result_ids_filters_unknown_ids():
    available = [{"id": "r1"}, {"id": "r2"}]

    ids = _normalize_referenced_result_ids(["r2", "missing", "r2", "r1"], available)

    assert ids == ["r2", "r1"]


def test_query_result_allowed_applies_table_whitelist():
    result = {"referenced_tables": ["table_a", "table_b"]}

    assert _query_result_allowed(result, ["table_a", "table_b"])
    assert not _query_result_allowed(result, ["table_a"])


def test_build_analysis_context_includes_stats_and_truncates_rows():
    rows = [[i, i * 2] for i in range(60)]
    result = {
        "columns": ["季度", "指标值"],
        "rows": rows,
        "row_count": 60,
    }
    context = _build_analysis_context(
        referenced_results=[{
            "id": "r1",
            "question": "查询指标",
            "summary": "指标摘要",
            "sql": "select 1",
            "result_data": result,
            "referenced_tables": ["table_a"],
        }],
    )

    assert "历史结果 1" in context
    assert "仅展示前 50 行" in context
    assert "数值列基础统计" in context
    assert "指标值" in context


def test_build_query_result_summary_uses_columns_and_row_count():
    summary = build_query_result_summary(
        "查询偿付能力指标",
        {"columns": ["公司", "指标"], "rows": [], "row_count": 3},
    )

    assert "返回 3 行" in summary
    assert "公司、指标" in summary


def test_rewrite_question_refreshes_downstream_question_fields(monkeypatch):
    class FakeRewriteChain:
        def __or__(self, _other):
            return self

        def invoke(self, _payload):
            return "改写后的查询问题"

    monkeypatch.setattr(nodes, "QUESTION_REWRITE_PROMPT", FakeRewriteChain())
    monkeypatch.setattr(nodes, "get_llm", lambda: object())

    result = rewrite_question_node({
        "question": "原始问题",
        "fused_question": "旧的融合问题",
        "sql_question": "旧的 SQL 问题",
        "log_context": None,
    })

    assert result["question"] == "改写后的查询问题"
    assert result["fused_question"] == "改写后的查询问题"
    assert result["sql_question"] == "改写后的查询问题"
    assert result["question_rewritten"] is True


class FakeFusionChain:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def __or__(self, _other):
        return self

    def invoke(self, payload):
        self.calls.append(payload)
        if callable(self.output):
            return self.output(payload)
        return self.output


def test_context_fusion_routes_without_history(monkeypatch):
    payload = {
        "question_type": "ambiguous",
        "intent_type": "clarify",
        "confidence": 0.8,
        "reasoning": "缺少可查询条件",
        "fused_question": "分析一下",
        "sql_question": "",
        "referenced_result_ids": [],
        "clarification_message": "请补充要查询的公司、指标或期间。",
    }
    fake_chain = FakeFusionChain(json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(nodes, "CONTEXT_FUSION_PROMPT", fake_chain)
    monkeypatch.setattr(nodes, "get_llm", lambda: object())

    result = context_fusion_node({"question": "分析一下", "log_context": None})

    assert fake_chain.calls[0]["conversation_history"] == "无"
    assert fake_chain.calls[0]["available_results"] == "无"
    assert result["intent_type"] == "clarify"
    assert result["clarification_message"] == "请补充要查询的公司、指标或期间。"


def test_context_fusion_only_defaults_history_result_on_explicit_reference(monkeypatch):
    def route_payload(payload):
        return json.dumps({
            "question_type": "continuation",
            "intent_type": "analysis",
            "confidence": 0.9,
            "reasoning": "用户要求分析历史结果",
            "fused_question": payload["question"],
            "sql_question": "",
            "referenced_result_ids": [],
            "clarification_message": "",
        }, ensure_ascii=False)

    fake_chain = FakeFusionChain(route_payload)
    monkeypatch.setattr(nodes, "CONTEXT_FUSION_PROMPT", fake_chain)
    monkeypatch.setattr(nodes, "get_llm", lambda: object())
    available_results = [{"id": "r1", "question": "查询指标", "summary": "摘要"}]

    unclear = context_fusion_node({
        "question": "分析一下",
        "available_results": available_results,
        "log_context": None,
    })
    explicit = context_fusion_node({
        "question": "分析刚才的结果",
        "available_results": available_results,
        "log_context": None,
    })

    assert unclear["intent_type"] == "clarify"
    assert unclear["referenced_result_ids"] == []
    assert explicit["intent_type"] == "analysis"
    assert explicit["referenced_result_ids"] == ["r1"]


def test_generate_answer_stream_clarify_does_not_call_llm(monkeypatch):
    monkeypatch.setattr(nodes, "get_llm", lambda: (_ for _ in ()).throw(AssertionError("LLM should not be called")))

    chunks = list(generate_answer_stream({
        "intent_type": "clarify",
        "clarification_message": "请补充要查询的公司、指标或期间。",
    }))

    assert chunks == [
        "请补充要查询的公司、指标或期间。",
        {"__explanation__": ""},
    ]
