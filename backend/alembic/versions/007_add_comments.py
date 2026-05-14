"""为 public 和 meta schema 下所有表及字段添加中文注释

Revision ID: 007
Revises: 006
Create Date: 2026-05-03
"""

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ══════════════════════════════════════════════════════════
    # public schema
    # ══════════════════════════════════════════════════════════

    # ── users ──────────────────────────────────────────────────
    op.execute("COMMENT ON TABLE users IS '用户账户表'")
    op.execute("COMMENT ON COLUMN users.id IS '用户唯一标识（UUID）'")
    op.execute("COMMENT ON COLUMN users.email IS '登录邮箱，全局唯一'")
    op.execute("COMMENT ON COLUMN users.hashed_password IS '密码 bcrypt 哈希值'")
    op.execute("COMMENT ON COLUMN users.full_name IS '用户姓名'")
    op.execute("COMMENT ON COLUMN users.is_active IS '账户是否启用'")
    op.execute("COMMENT ON COLUMN users.created_at IS '账户创建时间'")
    op.execute("COMMENT ON COLUMN users.updated_at IS '账户最后更新时间'")

    # ── roles ──────────────────────────────────────────────────
    op.execute("COMMENT ON TABLE roles IS 'RBAC 角色表'")
    op.execute("COMMENT ON COLUMN roles.id IS '角色唯一标识（UUID）'")
    op.execute("COMMENT ON COLUMN roles.name IS '角色名称，唯一（admin / analyst / viewer）'")
    op.execute("COMMENT ON COLUMN roles.description IS '角色描述'")

    # ── user_roles ─────────────────────────────────────────────
    op.execute("COMMENT ON TABLE user_roles IS '用户与角色多对多关联表'")
    op.execute("COMMENT ON COLUMN user_roles.user_id IS '关联用户 ID'")
    op.execute("COMMENT ON COLUMN user_roles.role_id IS '关联角色 ID'")

    # ── permissions ────────────────────────────────────────────
    op.execute("COMMENT ON TABLE permissions IS '细粒度权限表'")
    op.execute("COMMENT ON COLUMN permissions.id IS '权限唯一标识（UUID）'")
    op.execute("COMMENT ON COLUMN permissions.resource_type IS '资源类型：schema 或 table'")
    op.execute("COMMENT ON COLUMN permissions.resource_name IS '资源名称：schema 名或表名'")
    op.execute("COMMENT ON COLUMN permissions.action IS '操作类型：read 或 write'")

    # ── role_permissions ───────────────────────────────────────
    op.execute("COMMENT ON TABLE role_permissions IS '角色与权限多对多关联表'")
    op.execute("COMMENT ON COLUMN role_permissions.role_id IS '关联角色 ID'")
    op.execute("COMMENT ON COLUMN role_permissions.permission_id IS '关联权限 ID'")

    # ── sessions ───────────────────────────────────────────────
    op.execute("COMMENT ON TABLE sessions IS '用户对话会话表'")
    op.execute("COMMENT ON COLUMN sessions.id IS '会话唯一标识（UUID）'")
    op.execute("COMMENT ON COLUMN sessions.user_id IS '所属用户 ID'")
    op.execute("COMMENT ON COLUMN sessions.title IS '会话标题'")
    op.execute("COMMENT ON COLUMN sessions.is_active IS '会话是否处于活跃状态'")
    op.execute("COMMENT ON COLUMN sessions.created_at IS '会话创建时间'")
    op.execute("COMMENT ON COLUMN sessions.updated_at IS '会话最后更新时间'")
    op.execute("COMMENT ON COLUMN sessions.auto_titled IS '标题是否由系统自动生成；false 表示用户已手动重命名'")

    # ── messages ───────────────────────────────────────────────
    op.execute("COMMENT ON TABLE messages IS '对话消息历史表'")
    op.execute("COMMENT ON COLUMN messages.id IS '消息唯一标识（UUID）'")
    op.execute("COMMENT ON COLUMN messages.session_id IS '所属会话 ID'")
    op.execute("COMMENT ON COLUMN messages.role IS '消息发送方：user 或 assistant'")
    op.execute("COMMENT ON COLUMN messages.content IS '消息正文内容'")
    op.execute("COMMENT ON COLUMN messages.metadata IS '附加元数据（JSON），如工具调用结果、引用来源等'")
    op.execute("COMMENT ON COLUMN messages.created_at IS '消息发送时间'")

    # ── audit_logs ─────────────────────────────────────────────
    op.execute("COMMENT ON TABLE audit_logs IS 'SQL 查询审计日志表'")
    op.execute("COMMENT ON COLUMN audit_logs.id IS '日志唯一标识（UUID）'")
    op.execute("COMMENT ON COLUMN audit_logs.user_id IS '发起查询的用户 ID'")
    op.execute("COMMENT ON COLUMN audit_logs.session_id IS '所属会话 ID'")
    op.execute("COMMENT ON COLUMN audit_logs.question IS '用户自然语言提问内容'")
    op.execute("COMMENT ON COLUMN audit_logs.generated_sql IS 'LLM 生成的 SQL 语句'")
    op.execute("COMMENT ON COLUMN audit_logs.execution_success IS 'SQL 是否执行成功'")
    op.execute("COMMENT ON COLUMN audit_logs.execution_time_ms IS 'SQL 执行耗时（毫秒）'")
    op.execute("COMMENT ON COLUMN audit_logs.row_count IS '查询返回的数据行数'")
    op.execute("COMMENT ON COLUMN audit_logs.error_message IS '执行失败时的错误信息'")
    op.execute("COMMENT ON COLUMN audit_logs.created_at IS '日志记录时间'")

    # ── refresh_tokens ─────────────────────────────────────────
    op.execute("COMMENT ON TABLE refresh_tokens IS 'JWT 刷新令牌表'")
    op.execute("COMMENT ON COLUMN refresh_tokens.id IS '令牌唯一标识（UUID）'")
    op.execute("COMMENT ON COLUMN refresh_tokens.user_id IS '所属用户 ID'")
    op.execute("COMMENT ON COLUMN refresh_tokens.token_hash IS '令牌 SHA-256 哈希值（hex 编码）'")
    op.execute("COMMENT ON COLUMN refresh_tokens.expires_at IS '令牌过期时间'")
    op.execute("COMMENT ON COLUMN refresh_tokens.revoked IS '是否已主动吊销'")
    op.execute("COMMENT ON COLUMN refresh_tokens.created_at IS '令牌签发时间'")

    # ── table_groups ───────────────────────────────────────────
    op.execute("COMMENT ON TABLE table_groups IS '表分组管理表，用于按组向角色授权数据表访问权限'")
    op.execute("COMMENT ON COLUMN table_groups.id IS '分组唯一标识（UUID）'")
    op.execute("COMMENT ON COLUMN table_groups.name IS '分组名称，全局唯一'")
    op.execute("COMMENT ON COLUMN table_groups.description IS '分组描述'")
    op.execute("COMMENT ON COLUMN table_groups.created_at IS '分组创建时间'")
    op.execute("COMMENT ON COLUMN table_groups.updated_at IS '分组最后更新时间'")

    # ── table_group_members ────────────────────────────────────
    op.execute("COMMENT ON TABLE table_group_members IS '表分组成员表，记录各分组包含的数据表'")
    op.execute("COMMENT ON COLUMN table_group_members.group_id IS '所属分组 ID'")
    op.execute("COMMENT ON COLUMN table_group_members.table_schema IS '数据表所在的 Schema 名'")
    op.execute("COMMENT ON COLUMN table_group_members.table_name IS '数据表名'")

    # ── role_table_groups ──────────────────────────────────────
    op.execute("COMMENT ON TABLE role_table_groups IS '角色与表分组多对多关联表'")
    op.execute("COMMENT ON COLUMN role_table_groups.role_id IS '关联角色 ID'")
    op.execute("COMMENT ON COLUMN role_table_groups.group_id IS '关联表分组 ID'")

    # ══════════════════════════════════════════════════════════
    # meta schema
    # ══════════════════════════════════════════════════════════

    # ── meta.logical_tables ────────────────────────────────────
    op.execute("COMMENT ON TABLE meta.logical_tables IS '逻辑表元数据目录，存储业务表的稳定标识与注释，与物理表名解耦'")
    op.execute("COMMENT ON COLUMN meta.logical_tables.id IS '逻辑表唯一标识（UUID）'")
    op.execute("COMMENT ON COLUMN meta.logical_tables.physical_schema IS '物理表所在 Schema 名，默认 sql_agent'")
    op.execute("COMMENT ON COLUMN meta.logical_tables.physical_name IS '物理表名'")
    op.execute("COMMENT ON COLUMN meta.logical_tables.table_comment IS '表业务注释，供 LLM 理解表含义'")
    op.execute("COMMENT ON COLUMN meta.logical_tables.update_strategy IS '数据更新策略：full_replace 全量替换 / upsert 增量更新 / append 追加 / versioned_append 版本追加'")
    op.execute("COMMENT ON COLUMN meta.logical_tables.business_key IS '业务主键字段名数组，用于 upsert 去重'")
    op.execute("COMMENT ON COLUMN meta.logical_tables.status IS '表状态：active 正常使用 / deprecated 已弃用'")
    op.execute("COMMENT ON COLUMN meta.logical_tables.created_by IS '创建该逻辑表记录的用户 ID'")
    op.execute("COMMENT ON COLUMN meta.logical_tables.created_at IS '记录创建时间'")
    op.execute("COMMENT ON COLUMN meta.logical_tables.updated_at IS '记录最后更新时间'")

    # ── meta.logical_columns ───────────────────────────────────
    op.execute("COMMENT ON TABLE meta.logical_columns IS '逻辑列元数据目录，存储字段的稳定标识、注释及物理映射关系'")
    op.execute("COMMENT ON COLUMN meta.logical_columns.id IS '逻辑列唯一标识（UUID）'")
    op.execute("COMMENT ON COLUMN meta.logical_columns.table_id IS '所属逻辑表 ID'")
    op.execute("COMMENT ON COLUMN meta.logical_columns.original_name IS '列原始名（来源文件中的列名或中文名）'")
    op.execute("COMMENT ON COLUMN meta.logical_columns.physical_name IS '物理列名（经 LLM 规范化后写入数据库的实际列名）'")
    op.execute("COMMENT ON COLUMN meta.logical_columns.column_comment IS '列业务注释，供 LLM 理解字段含义'")
    op.execute("COMMENT ON COLUMN meta.logical_columns.ordinal_position IS '列在表中的排列顺序（从 1 开始）'")
    op.execute("COMMENT ON COLUMN meta.logical_columns.data_type IS 'PostgreSQL 数据类型字符串，如 TEXT、INTEGER、NUMERIC 等'")
    op.execute("COMMENT ON COLUMN meta.logical_columns.is_active IS '是否为活跃列；false 表示该列已从源表移除（软删除）'")
    op.execute("COMMENT ON COLUMN meta.logical_columns.created_at IS '记录创建时间'")
    op.execute("COMMENT ON COLUMN meta.logical_columns.updated_at IS '记录最后更新时间'")

    # ── meta.upload_history ────────────────────────────────────
    op.execute("COMMENT ON TABLE meta.upload_history IS '文件上传历史表，记录每次数据文件上传及审核流转过程'")
    op.execute("COMMENT ON COLUMN meta.upload_history.id IS '上传记录唯一标识（UUID）'")
    op.execute("COMMENT ON COLUMN meta.upload_history.table_id IS '关联逻辑表 ID；新建表时为 NULL'")
    op.execute("COMMENT ON COLUMN meta.upload_history.file_hash IS '文件内容 SHA-256 哈希，用于去重'")
    op.execute("COMMENT ON COLUMN meta.upload_history.file_name IS '原始上传文件名'")
    op.execute("COMMENT ON COLUMN meta.upload_history.file_size IS '文件大小（字节）'")
    op.execute("COMMENT ON COLUMN meta.upload_history.stored_path IS '文件在服务器上的存储路径'")
    op.execute("COMMENT ON COLUMN meta.upload_history.uploaded_by IS '上传操作人用户 ID'")
    op.execute("COMMENT ON COLUMN meta.upload_history.uploaded_at IS '文件上传时间'")
    op.execute("COMMENT ON COLUMN meta.upload_history.status IS '审核状态：pending_review 待审 / confirmed 已确认 / rejected 已拒绝 / applied 已应用 / failed 失败'")
    op.execute("COMMENT ON COLUMN meta.upload_history.action_type IS '操作类型：new_table 新建表 / schema_change 字段变更 / data_only 仅数据刷新'")
    op.execute("COMMENT ON COLUMN meta.upload_history.llm_proposal IS 'LLM 生成的字段映射建议（JSON），包含推荐列名及注释'")
    op.execute("COMMENT ON COLUMN meta.upload_history.diff_summary IS '与上次版本的字段变更摘要（JSON）'")
    op.execute("COMMENT ON COLUMN meta.upload_history.error_message IS '处理或应用失败时的错误信息'")
    op.execute("COMMENT ON COLUMN meta.upload_history.applied_at IS '审核通过并成功应用到数据库的时间'")

    # ── meta.schema_changes ────────────────────────────────────
    op.execute("COMMENT ON TABLE meta.schema_changes IS 'Schema 变更审计日志表，逐字段记录元数据变更历史'")
    op.execute("COMMENT ON COLUMN meta.schema_changes.id IS '变更记录唯一标识（UUID）'")
    op.execute("COMMENT ON COLUMN meta.schema_changes.table_id IS '发生变更的逻辑表 ID'")
    op.execute("COMMENT ON COLUMN meta.schema_changes.upload_history_id IS '触发此次变更的上传历史 ID'")
    op.execute("COMMENT ON COLUMN meta.schema_changes.change_type IS '变更类型：add_col 新增列 / drop_col 删除列 / comment_update 注释更新'")
    op.execute("COMMENT ON COLUMN meta.schema_changes.column_id IS '涉及变更的逻辑列 ID'")
    op.execute("COMMENT ON COLUMN meta.schema_changes.before_state IS '变更前的列状态快照（JSON）'")
    op.execute("COMMENT ON COLUMN meta.schema_changes.after_state IS '变更后的列状态快照（JSON）'")
    op.execute("COMMENT ON COLUMN meta.schema_changes.applied_at IS '变更应用时间'")
    op.execute("COMMENT ON COLUMN meta.schema_changes.applied_by IS '执行变更操作的用户 ID'")

    # ── meta.vector_sync_log ───────────────────────────────────
    op.execute("COMMENT ON TABLE meta.vector_sync_log IS '向量库（Milvus）同步日志表，追踪表/列元数据向量化的同步状态'")
    op.execute("COMMENT ON COLUMN meta.vector_sync_log.id IS '同步记录唯一标识（UUID）'")
    op.execute("COMMENT ON COLUMN meta.vector_sync_log.target_id IS '同步目标的 ID，对应逻辑表或逻辑列的 ID'")
    op.execute("COMMENT ON COLUMN meta.vector_sync_log.target_type IS '同步目标类型：table 表级 / column 列级'")
    op.execute("COMMENT ON COLUMN meta.vector_sync_log.op IS '同步操作类型：upsert 写入或更新 / delete 删除'")
    op.execute("COMMENT ON COLUMN meta.vector_sync_log.status IS '同步状态：pending 待同步 / success 成功 / pending_retry 等待重试 / failed 失败'")
    op.execute("COMMENT ON COLUMN meta.vector_sync_log.attempts IS '已执行的同步尝试次数'")
    op.execute("COMMENT ON COLUMN meta.vector_sync_log.last_error IS '最近一次同步失败的错误信息'")
    op.execute("COMMENT ON COLUMN meta.vector_sync_log.payload_hash IS '同步内容的哈希值，用于检测注释是否发生变更'")
    op.execute("COMMENT ON COLUMN meta.vector_sync_log.created_at IS '同步任务创建时间'")
    op.execute("COMMENT ON COLUMN meta.vector_sync_log.updated_at IS '同步任务最后更新时间'")


def downgrade() -> None:
    # ── meta schema ────────────────────────────────────────────
    op.execute("COMMENT ON TABLE meta.vector_sync_log IS NULL")
    op.execute("COMMENT ON TABLE meta.schema_changes IS NULL")
    op.execute("COMMENT ON TABLE meta.upload_history IS NULL")
    op.execute("COMMENT ON TABLE meta.logical_columns IS NULL")
    op.execute("COMMENT ON TABLE meta.logical_tables IS NULL")

    # ── public schema ──────────────────────────────────────────
    op.execute("COMMENT ON TABLE role_table_groups IS NULL")
    op.execute("COMMENT ON TABLE table_group_members IS NULL")
    op.execute("COMMENT ON TABLE table_groups IS NULL")
    op.execute("COMMENT ON TABLE refresh_tokens IS NULL")
    op.execute("COMMENT ON TABLE audit_logs IS NULL")
    op.execute("COMMENT ON TABLE messages IS NULL")
    op.execute("COMMENT ON TABLE sessions IS NULL")
    op.execute("COMMENT ON TABLE role_permissions IS NULL")
    op.execute("COMMENT ON TABLE permissions IS NULL")
    op.execute("COMMENT ON TABLE user_roles IS NULL")
    op.execute("COMMENT ON TABLE roles IS NULL")
    op.execute("COMMENT ON TABLE users IS NULL")
