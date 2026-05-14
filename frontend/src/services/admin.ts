import { api } from './api'
import type {
  Role, RoleDetail, GroupRef,
  TableInfo, TableDetail,
  TableGroup, TableGroupDetail, TableRef,
  UserItem,
  UploadAcceptedResponse, UploadBatchDetail, UploadBatchSummary,
  VectorSyncLogEntry,
} from '../types/admin'

// ── 用户 ──
export const UsersAPI = {
  list: () => api.get<UserItem[]>('/admin/users').then((r) => r.data),
  create: (body: {
    email: string; password: string; full_name?: string; roles: string[]
  }) => api.post<UserItem>('/admin/users', body).then((r) => r.data),
  update: (id: string, body: { full_name?: string; password?: string }) =>
    api.put<UserItem>(`/admin/users/${id}`, body).then((r) => r.data),
  toggleActive: (id: string, is_active: boolean) =>
    api.put<UserItem>(`/admin/users/${id}/active`, { is_active }).then((r) => r.data),
  setRoles: (id: string, roles: string[]) =>
    api.put<UserItem>(`/admin/users/${id}/roles`, { roles }).then((r) => r.data),
  remove: (id: string) => api.delete(`/admin/users/${id}`),
}

// ── 角色 ──
export const RolesAPI = {
  list: () => api.get<Role[]>('/admin/roles').then((r) => r.data),
  detail: (id: string) => api.get<RoleDetail>(`/admin/roles/${id}`).then((r) => r.data),
  create: (body: { name: string; description?: string }) =>
    api.post<Role>('/admin/roles', body).then((r) => r.data),
  update: (id: string, body: { name?: string; description?: string }) =>
    api.put<Role>(`/admin/roles/${id}`, body).then((r) => r.data),
  remove: (id: string) => api.delete(`/admin/roles/${id}`),
  getGroups: (id: string) =>
    api.get<GroupRef[]>(`/admin/roles/${id}/table-groups`).then((r) => r.data),
  setGroups: (id: string, group_ids: string[]) =>
    api.put<string[]>(`/admin/roles/${id}/table-groups`, { group_ids }).then((r) => r.data),
}

// ── 业务数据表 ──
export const TablesAPI = {
  list: () => api.get<TableInfo[]>('/admin/tables').then((r) => r.data),
  schema: () => api.get<{ schema: string }>('/admin/tables/schema').then((r) => r.data),
  detail: (name: string) =>
    api.get<TableDetail>(`/admin/tables/${encodeURIComponent(name)}`).then((r) => r.data),

  upload: (files: File | File[], groupId: string, targetTableIdOrIds?: string | string[]) => {
    const fd = new FormData()
    const selectedFiles = Array.isArray(files) ? files : [files]
    selectedFiles.forEach((file) => fd.append('files', file))
    fd.append('group_id', groupId)
    if (Array.isArray(targetTableIdOrIds)) {
      fd.append('mode', 'update')
      targetTableIdOrIds.forEach((id) => fd.append('target_table_ids', id))
      fd.append('target_table_ids_json', JSON.stringify(targetTableIdOrIds))
    } else if (targetTableIdOrIds) {
      fd.append('mode', 'update')
      fd.append('target_table_id', targetTableIdOrIds)
    } else {
      fd.append('mode', 'new')
    }
    return api.post<UploadAcceptedResponse>('/admin/tables/upload', fd).then((r) => r.data)
  },
  uploadBatches: (limit = 50) =>
    api.get<UploadBatchSummary[]>('/admin/tables/upload-batches', { params: { limit } }).then((r) => r.data),
  uploadBatchDetail: (batchId: string) =>
    api.get<UploadBatchDetail>(`/admin/tables/upload-batches/${batchId}`).then((r) => r.data),

  updateDisplayName: (tableId: string, displayName: string) =>
    api.put<any>(`/admin/tables/${tableId}/display-name`, { display_name: displayName }).then((r) => r.data),
  updateTableComment: (tableId: string, comment: string) =>
    api.put<any>(`/admin/tables/${tableId}/comment`, { comment }).then((r) => r.data),
  updateMetadata: (tableId: string, displayName: string, comment: string) =>
    api.put<any>(`/admin/tables/${tableId}/metadata`, {
      display_name: displayName,
      comment,
    }).then((r) => r.data),
  updateColumnComment: (tableId: string, colId: string, comment: string) =>
    api.put<any>(`/admin/tables/${tableId}/columns/${colId}/comment`, { comment }).then((r) => r.data),
  deleteMany: (tableIds: string[]) =>
    api.delete<{ deleted: string[]; errors: Array<{ id: string; error: string }> }>(
      '/admin/tables/batch', { data: { table_ids: tableIds } }
    ).then((r) => r.data),
}

// ── 向量库（Milvus 版）──
export const VectorstoreAPI = {
  status: () => api.get<{ table_count: number; column_count: number; ready: boolean }>('/admin/vectorstore/status').then((r) => r.data),
  sync: () => api.post<any>('/admin/vectorstore/sync').then((r) => r.data),
  rebuild: () => api.post<any>('/admin/vectorstore/rebuild').then((r) => r.data),
  retry: () => api.post<any>('/admin/vectorstore/retry').then((r) => r.data),
  syncLog: (limit = 50) =>
    api.get<VectorSyncLogEntry[]>('/admin/vectorstore/sync-log', { params: { limit } }).then((r) => r.data),
}

// ── 表分组 ──
export const TableGroupsAPI = {
  list: () => api.get<TableGroup[]>('/admin/table-groups').then((r) => r.data),
  detail: (id: string) =>
    api.get<TableGroupDetail>(`/admin/table-groups/${id}`).then((r) => r.data),
  create: (body: { name: string; description?: string }) =>
    api.post<TableGroup>('/admin/table-groups', body).then((r) => r.data),
  update: (id: string, body: { name?: string; description?: string }) =>
    api.put<TableGroup>(`/admin/table-groups/${id}`, body).then((r) => r.data),
  remove: (id: string) => api.delete(`/admin/table-groups/${id}`),
  getTables: (id: string) =>
    api.get<TableRef[]>(`/admin/table-groups/${id}/tables`).then((r) => r.data),
  setTables: (id: string, tables: TableRef[]) =>
    api.put<TableRef[]>(`/admin/table-groups/${id}/tables`, { tables }).then((r) => r.data),
}
