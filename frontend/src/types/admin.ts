export interface UserItem {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
  roles: string[]
  created_at: string
  last_login?: string
}

export interface GroupRef {
  id: string
  name: string
  description: string | null
  table_count: number
}

export interface Role {
  id: string
  name: string
  description: string | null
  is_builtin: boolean
  group_count: number
  user_count: number
}

export interface RoleDetail extends Role {
  groups: GroupRef[]
}

export interface GroupTag {
  id: string
  name: string
}

export interface TableInfo {
  id: string | null
  name: string
  schema: string
  display_name: string | null
  comment: string | null
  column_count: number
  groups: GroupTag[]
}

export interface ColumnInfo {
  id: string | null
  name: string
  original_name: string | null
  data_type: string
  nullable: boolean
  is_primary_key: boolean
  comment: string | null
}

export interface TableDetail {
  id: string | null
  name: string
  schema: string
  display_name: string | null
  comment: string | null
  columns: ColumnInfo[]
  groups: GroupTag[]
}

export interface TableGroup {
  id: string
  name: string
  description: string | null
  table_count: number
  role_count: number
}

export interface TableRef {
  schema: string
  name: string
}

export interface TableGroupDetail extends TableGroup {
  tables: TableRef[]
}

export type ActionType = 'new_table' | 'data_only' | 'schema_change'

export type UploadBatchStatus = 'queued' | 'processing' | 'success' | 'partial_failed' | 'failed'
export type UploadBatchItemStatus = 'queued' | 'processing' | 'applied' | 'failed'
export type UploadMode = 'new' | 'update'

export interface UploadAcceptedResponse {
  batch_id: string
  count: number
  status: UploadBatchStatus
  message: string
}

export interface UploadBatchSummary {
  id: string
  group_id: string | null
  group_name: string | null
  target_table_id: string | null
  mode: UploadMode
  status: UploadBatchStatus
  total_count: number
  success_count: number
  failed_count: number
  error_message: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface UploadBatchItem {
  id: string
  batch_id: string
  upload_history_id: string | null
  table_id: string | null
  file_name: string
  file_size: number | null
  status: UploadBatchItemStatus
  action_type: ActionType | null
  error_message: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface UploadBatchDetail extends UploadBatchSummary {
  items: UploadBatchItem[]
}

export interface VectorSyncLogEntry {
  id: string
  target_id: string
  target_type: 'table' | 'column'
  op: 'upsert' | 'delete'
  status: 'pending' | 'success' | 'pending_retry' | 'failed'
  attempts: number
  last_error: string | null
  created_at: string
  updated_at: string
}
