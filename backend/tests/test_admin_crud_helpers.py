import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.admin_data_pipeline.validation import (
    is_valid_identifier,
    normalize_new_table_proposal,
    quote_identifier,
    validate_upload_file_count,
)


def test_normalize_new_table_proposal_sanitizes_identifiers_and_types():
    proposal = {
        "table_name": "SELECT * FROM",
        "display_name": "测试表",
        "table_comment": "测试表注释",
        "columns": [
            {"original_name": "公司 名", "column_name": "公司 名", "column_comment": "公司"},
            {"original_name": "金额", "column_name": "select", "data_type": "DROP TABLE x"},
        ],
    }

    normalized = normalize_new_table_proposal(
        proposal,
        ["公司 名", "金额"],
        existing_table_names={"select_from"},
    )

    assert normalized["table_name"] == "select_from_2"
    assert is_valid_identifier(normalized["table_name"])
    assert normalized["columns"][0]["column_name"] == "col_1"
    assert normalized["columns"][1]["column_name"] == "col_2"
    assert normalized["columns"][1]["data_type"] == "TEXT"


def test_normalize_new_table_proposal_reorders_by_original_name():
    proposal = {
        "table_name": "claims",
        "columns": [
            {"original_name": "金额", "column_name": "amount"},
            {"original_name": "公司", "column_name": "company"},
        ],
    }

    normalized = normalize_new_table_proposal(proposal, ["公司", "金额"])

    assert [c["original_name"] for c in normalized["columns"]] == ["公司", "金额"]
    assert [c["column_name"] for c in normalized["columns"]] == ["company", "amount"]


def test_normalize_new_table_proposal_rejects_bad_column_shape():
    proposal = {"table_name": "claims", "columns": [{"column_name": "company"}]}

    with pytest.raises(ValueError, match="字段数量"):
        normalize_new_table_proposal(proposal, ["公司", "金额"])


def test_normalize_new_table_proposal_rejects_duplicate_file_columns():
    proposal = {
        "table_name": "claims",
        "columns": [{"column_name": "company"}, {"column_name": "company_2"}],
    }

    with pytest.raises(ValueError, match="重复字段"):
        normalize_new_table_proposal(proposal, ["公司", "公司"])


def test_quote_identifier_escapes_double_quotes():
    assert quote_identifier('bad"name') == '"bad""name"'


def test_validate_upload_file_count_allows_new_table_batch_limit():
    assert validate_upload_file_count(20, None, mode="new") == [None] * 20


def test_validate_upload_file_count_rejects_new_table_over_limit():
    with pytest.raises(ValueError, match="最多上传 20 个文件"):
        validate_upload_file_count(21, None)


def test_validate_upload_file_count_allows_legacy_single_file_update():
    assert validate_upload_file_count(1, "table-1", mode="update") == ["table-1"]


def test_validate_upload_file_count_rejects_legacy_multi_file_update():
    with pytest.raises(ValueError, match="target_table_id 仅支持 1 个文件"):
        validate_upload_file_count(2, "table-1")


def test_validate_upload_file_count_allows_batch_update_mapping():
    assert validate_upload_file_count(
        2,
        None,
        target_table_ids=["table-1", "table-2"],
        mode="update",
    ) == ["table-1", "table-2"]


def test_validate_upload_file_count_rejects_batch_update_count_mismatch():
    with pytest.raises(ValueError, match="每个文件选择一个目标表"):
        validate_upload_file_count(2, None, target_table_ids=["table-1"])


def test_validate_upload_file_count_rejects_duplicate_batch_update_targets():
    with pytest.raises(ValueError, match="不能重复选择同一张表"):
        validate_upload_file_count(2, None, target_table_ids=["table-1", "table-1"])


def test_validate_upload_file_count_rejects_update_without_targets():
    with pytest.raises(ValueError, match="更新已有表需要选择目标表"):
        validate_upload_file_count(1, None, mode="update")


def test_validate_upload_file_count_rejects_new_mode_with_targets():
    with pytest.raises(ValueError, match="新建表不能选择目标表"):
        validate_upload_file_count(1, "table-1", mode="new")
