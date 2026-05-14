import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.admin_data_pipeline.identifier import decide_action
from services.admin_data_pipeline.merger import (
    _choose_dedupe_columns,
    _df_to_rows,
    _filter_new_rows,
    _plan_new_columns,
)
from services.admin_data_pipeline import staging
from services.admin_data_pipeline.upload_batches import (
    _decide_action_sync,
    _get_item_target_table_id,
    _require_update_target_table_id,
    _resolve_item_target_table_ids,
    _should_reject_duplicate_file,
    _validate_target_tables_sync,
)
from services.admin_data_pipeline.validation import normalize_schema_change_columns


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeSyncConn:
    def __init__(self, original_names):
        self.original_names = original_names

    def execute(self, statement, params=None):
        return _Result([SimpleNamespace(original_name=name) for name in self.original_names])


class _MappingRow:
    def __init__(self, **values):
        self._mapping = values
        for key, value in values.items():
            setattr(self, key, value)


class _AsyncResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeAsyncSession:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, statement, params=None):
        return _AsyncResult(self.rows)


def test_update_action_allows_same_or_missing_columns_and_detects_new_columns():
    conn = _FakeSyncConn(["公司", "季度", "金额"])

    assert _decide_action_sync(conn, {"columns": ["公司", "季度", "金额"]}, "t1") == ("data_only", "t1")
    assert _decide_action_sync(conn, {"columns": ["公司", "季度"]}, "t1") == ("data_only", "t1")
    assert _decide_action_sync(conn, {"columns": ["公司", "季度", "金额", "备注"]}, "t1") == ("schema_change", "t1")


def test_batch_update_item_target_overrides_batch_target():
    assert _get_item_target_table_id(
        {"target_table_id": "legacy-table"},
        {"table_id": "item-table"},
    ) == "item-table"
    assert _get_item_target_table_id(
        {"target_table_id": "legacy-table"},
        {"table_id": None},
    ) == "legacy-table"


def test_update_batch_without_item_or_batch_target_is_rejected():
    with pytest.raises(ValueError, match="更新已有表缺少目标表"):
        _require_update_target_table_id(
            {"mode": "update", "target_table_id": None},
            {"table_id": None},
        )


def test_resolve_item_target_table_ids_keeps_file_order():
    files = [object(), object()]

    assert _resolve_item_target_table_ids(files, None, ["table-1", "table-2"]) == ["table-1", "table-2"]
    assert _resolve_item_target_table_ids(files[:1], "legacy-table", None) == ["legacy-table"]
    with pytest.raises(ValueError, match="每个文件选择一个目标表"):
        _resolve_item_target_table_ids(files, None, ["table-1"])


class _FetchOneResult:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _TargetValidationConn:
    def __init__(self, valid_table_ids):
        self.valid_table_ids = set(valid_table_ids)

    def execute(self, statement, params=None):
        return _FetchOneResult(object() if params["tid"] in self.valid_table_ids else None)


def test_validate_target_tables_rejects_table_outside_group():
    conn = _TargetValidationConn({"table-1"})

    _validate_target_tables_sync(conn, "group-1", ["table-1"])
    with pytest.raises(ValueError, match="目标表不存在或不属于所选分组"):
        _validate_target_tables_sync(conn, "group-1", ["table-2"])


@pytest.mark.asyncio
async def test_identifier_backup_allows_update_schema_drift():
    rows = [
        _MappingRow(id="c1", original_name="公司", physical_name="company", column_comment="", ordinal_position=1, data_type="TEXT"),
        _MappingRow(id="c2", original_name="季度", physical_name="quarter", column_comment="", ordinal_position=2, data_type="TEXT"),
    ]
    session = _FakeAsyncSession(rows)

    subset = await decide_action(session, {"columns": ["公司"]}, "t1")
    extra = await decide_action(session, {"columns": ["公司", "季度", "备注"]}, "t1")

    assert subset.action_type == "data_only"
    assert extra.action_type == "schema_change"


def test_schema_change_proposal_normalization_uses_llm_names_comments_and_text_type():
    proposal = {
        "table_name": "ignored",
        "columns": [
            {"original_name": "新增字段", "column_name": "new_metric", "column_comment": "新增指标说明"},
            {"original_name": "amount", "column_name": "amount", "column_comment": "补充金额说明"},
        ],
    }

    normalized = normalize_schema_change_columns(proposal, ["新增字段", "amount"], {"amount"})

    assert normalized == [
        {
            "original_name": "新增字段",
            "column_name": "new_metric",
            "column_comment": "新增指标说明",
            "data_type": "TEXT",
        },
        {
            "original_name": "amount",
            "column_name": "amount_2",
            "column_comment": "补充金额说明",
            "data_type": "TEXT",
        },
    ]


def test_plan_new_columns_uses_llm_proposal_and_text_type():
    existing_cols = [
        {"original_name": "公司", "physical_name": "company", "ordinal_position": 1},
        {"original_name": "金额", "physical_name": "amount", "ordinal_position": 2},
    ]

    planned = _plan_new_columns(
        ["公司", "新增字段", "amount"],
        existing_cols,
        proposed_columns=[
            {"original_name": "新增字段", "column_name": "new_metric", "column_comment": "新增指标说明"},
            {"original_name": "amount", "column_name": "amount", "column_comment": "补充金额说明"},
        ],
        used_physical_names={"amount"},
    )

    assert [c["original_name"] for c in planned] == ["新增字段", "amount"]
    assert [c["ordinal_position"] for c in planned] == [3, 4]
    assert [c["data_type"] for c in planned] == ["TEXT", "TEXT"]
    assert planned[0]["column_comment"] == "新增指标说明"
    assert planned[0]["physical_name"] == "new_metric"
    assert planned[1]["column_comment"] == "补充金额说明"
    assert planned[1]["physical_name"] == "amount_2"


class _ExistsResult:
    def __init__(self, found):
        self.found = found

    def fetchone(self):
        return object() if self.found else None


class _ExistingRowsConn:
    def __init__(self, existing_keys):
        self.existing_keys = existing_keys

    def execute(self, statement, params=None):
        ordered = tuple(params[f"v{i}"] for i in range(len(params or {})))
        return _ExistsResult(ordered in self.existing_keys)


def test_incremental_filter_skips_existing_and_upload_duplicate_rows():
    cols = [
        {"original_name": "公司", "physical_name": "company"},
        {"original_name": "季度", "physical_name": "quarter"},
        {"original_name": "金额", "physical_name": "amount"},
        {"original_name": "缺失旧列", "physical_name": "missing_old"},
    ]
    dedupe_cols = cols[:2]
    df = pd.DataFrame({
        "公司": ["A", "B", "B", "C"],
        "季度": ["2024Q1", "2024Q3", "2024Q3", "2024Q4"],
        "金额": [100, 200, 300, None],
    })

    filtered = _filter_new_rows(
        _ExistingRowsConn({("A", "2024Q1")}),
        "sql_agent",
        "target_table",
        cols,
        df,
        dedupe_cols,
    )

    assert filtered["公司"].tolist() == ["B", "C"]
    assert filtered["金额"].iloc[0] == 200.0
    assert pd.isna(filtered["金额"].iloc[1])

    rows = _df_to_rows(cols, filtered, ["v0", "v1", "v2", "v3"])
    assert rows[0]["v3"] is None
    assert rows[1]["v2"] is None


def test_dedupe_falls_back_to_uploaded_columns_when_no_old_columns_overlap():
    existing_cols = [{"original_name": "公司", "physical_name": "company"}]
    new_cols = [
        {"original_name": "新字段A", "physical_name": "col_2"},
        {"original_name": "新字段B", "physical_name": "col_3"},
    ]

    dedupe_cols = _choose_dedupe_columns(["新字段A", "新字段B"], existing_cols, [*existing_cols, *new_cols])

    assert [c["original_name"] for c in dedupe_cols] == ["新字段A", "新字段B"]


def test_duplicate_file_rejection_only_applies_to_new_table_uploads():
    assert _should_reject_duplicate_file("new_table") is True
    assert _should_reject_duplicate_file("data_only") is False
    assert _should_reject_duplicate_file("schema_change") is False


def test_staged_path_resolution_does_not_depend_on_worker_cwd(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    backend_root = project_root / "backend"
    project_file = project_root / "upload_staging" / "user-1" / "file.xlsx"
    backend_file = backend_root / "upload_staging" / "user-2" / "file.xlsx"
    project_file.parent.mkdir(parents=True)
    backend_file.parent.mkdir(parents=True)
    project_file.write_text("root", encoding="utf-8")
    backend_file.write_text("backend", encoding="utf-8")

    monkeypatch.setattr(staging, "_project_root", lambda: project_root)
    monkeypatch.setattr(staging, "_backend_root", lambda: backend_root)
    monkeypatch.chdir(backend_root)

    assert staging.resolve_staged_path(r"upload_staging\user-1\file.xlsx") == project_file.resolve()
    assert staging.resolve_staged_path(r"upload_staging\user-2\file.xlsx") == backend_file.resolve()
    assert staging.resolve_upload_staging_dir("./upload_staging") == (project_root / "upload_staging").resolve()
