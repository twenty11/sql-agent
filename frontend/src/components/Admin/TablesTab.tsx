import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { colors, radii, fontFamily } from '../../styles/tokens'
import { TablesAPI, TableGroupsAPI } from '../../services/admin'
import type { TableInfo, TableDetail, TableGroup, TableRef } from '../../types/admin'
import { useUploadTasks } from '../../contexts/UploadTasksContext'
import {
  Modal, CustomSelect, SelectOption,
  inputStyle, primaryBtnStyle, secondaryBtnStyle, dangerBtnStyle, labelStyle,
} from './shared'
import { CloseIcon } from '../Icons'
import { Tooltip } from '../ui/Tooltip'

const keyOf = (t: { schema: string; name: string }) => `${t.schema}.${t.name}`
const MAX_NEW_TABLE_UPLOAD_FILES = 20

// ─────────────────────────────────────────────────────────────────
// 主组件
// ─────────────────────────────────────────────────────────────────

export function TablesTab() {
  const [tables, setTables] = useState<TableInfo[]>([])
  const [groups, setGroups] = useState<TableGroup[]>([])
  const [groupFilter, setGroupFilter] = useState<string>('all')
  const [nameSearch, setNameSearch] = useState('')

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const [showUpload, setShowUpload] = useState(false)
  const [showGroupManage, setShowGroupManage] = useState(false)
  const [detailTarget, setDetailTarget] = useState<TableDetail | null>(null)
  const [editMetaTarget, setEditMetaTarget] = useState<TableDetail | null>(null)

  const load = useCallback(async () => {
    const [ts, gs] = await Promise.all([TablesAPI.list(), TableGroupsAPI.list()])
    setTables(ts)
    setGroups(gs)
    setSelectedIds(new Set())
  }, [])

  useEffect(() => { load().catch(() => {}) }, [load])
  useEffect(() => {
    const handler = () => { load().catch(() => {}) }
    window.addEventListener('upload-batches-updated', handler)
    return () => window.removeEventListener('upload-batches-updated', handler)
  }, [load])

  const filtered = useMemo(() => {
    let result = tables
    if (groupFilter !== 'all') {
      result = result.filter((t) => t.groups.some((g) => g.id === groupFilter))
    }
    if (nameSearch.trim()) {
      const kw = nameSearch.trim().toLowerCase()
      result = result.filter(
        (t) =>
          t.name.toLowerCase().includes(kw) ||
          (t.display_name || '').toLowerCase().includes(kw) ||
          (t.comment || '').toLowerCase().includes(kw),
      )
    }
    return result
  }, [tables, groupFilter, nameSearch])

  const groupOptions: SelectOption[] = [
    { value: 'all', label: '全部分组' },
    ...groups.map((g) => ({ value: g.id, label: `${g.name}（${g.table_count}）` })),
  ]

  const openDetail = async (name: string) => {
    try {
      setDetailTarget(await TablesAPI.detail(name))
    } catch (e: any) {
      alert(e?.response?.data?.detail || '加载表详情失败')
    }
  }

  const handleAfterUpload = () => {
    setShowUpload(false)
  }

  // 全选/取消全选
  const allFilteredIds = filtered.map((t) => t.id).filter(Boolean) as string[]
  const allSelected = allFilteredIds.length > 0 && allFilteredIds.every((id) => selectedIds.has(id))
  const toggleAll = () => {
    if (allSelected) {
      const next = new Set(selectedIds)
      allFilteredIds.forEach((id) => next.delete(id))
      setSelectedIds(next)
    } else {
      const next = new Set(selectedIds)
      allFilteredIds.forEach((id) => next.add(id))
      setSelectedIds(next)
    }
  }
  const toggleOne = (id: string) => {
    const next = new Set(selectedIds)
    if (next.has(id)) next.delete(id); else next.add(id)
    setSelectedIds(next)
  }

  const handleDeleteSelected = async () => {
    const ids = Array.from(selectedIds)
    setDeleting(true)
    try {
      const res = await TablesAPI.deleteMany(ids)
      if (res.errors.length > 0) {
        alert(`部分删除失败：${res.errors.map((e) => e.error).join('；')}`)
      }
      await load()
    } catch (e: any) {
      alert(e?.response?.data?.detail || '删除失败')
    } finally {
      setDeleting(false)
      setShowDeleteConfirm(false)
    }
  }

  const COL_WIDTHS = { checkbox: 40, name: 170, comment: 'auto', cols: 80, groups: 180, ops: 110 }

  return (
    <>
      {/* 顶部筛选栏 */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        <CustomSelect
          value={groupFilter}
          onChange={setGroupFilter}
          options={groupOptions}
          style={{ width: 180 }}
        />
        <input
          value={nameSearch}
          onChange={(e) => setNameSearch(e.target.value)}
          placeholder="表名搜索…"
          style={{ ...inputStyle, width: 200, height: 36 }}
        />
        {selectedIds.size > 0 && (
          <button
            onClick={() => setShowDeleteConfirm(true)}
            style={{ ...dangerBtnStyle, padding: '7px 14px', fontSize: 13 }}
          >
            删除选中（{selectedIds.size}）
          </button>
        )}
        <div style={{ flex: 1 }} />
        <button onClick={() => setShowUpload(true)} style={primaryBtnStyle}>
          上传数据文件
        </button>
        <button onClick={() => setShowGroupManage(true)} style={secondaryBtnStyle}>
          管理分组
        </button>
      </div>

      {/* 主表格 */}
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, tableLayout: 'fixed' }}>
        <colgroup>
          <col style={{ width: COL_WIDTHS.checkbox }} />
          <col style={{ width: COL_WIDTHS.name }} />
          <col />
          <col style={{ width: COL_WIDTHS.cols }} />
          <col style={{ width: COL_WIDTHS.groups }} />
          <col style={{ width: COL_WIDTHS.ops }} />
        </colgroup>
        <thead>
          <tr style={{ background: colors.sidebarBg, borderBottom: `1px solid ${colors.border}` }}>
            <th style={{ padding: '8px 12px', textAlign: 'center' }}>
              <input
                type="checkbox"
                checked={allSelected}
                onChange={toggleAll}
                disabled={allFilteredIds.length === 0}
              />
            </th>
            {['表名', '表注释', '字段数', '所属分组', '操作'].map((h) => (
              <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: colors.textSecondary }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filtered.length === 0 && (
            <tr>
              <td colSpan={6} style={{ padding: 32, textAlign: 'center', color: colors.textSecondary }}>
                暂无数据
              </td>
            </tr>
          )}
          {filtered.map((t) => (
            <tr key={t.name} style={{ borderBottom: `1px solid ${colors.border}`, background: t.id && selectedIds.has(t.id) ? colors.accent + '08' : undefined }}>
              <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                {t.id && (
                  <input
                    type="checkbox"
                    checked={selectedIds.has(t.id)}
                    onChange={() => toggleOne(t.id!)}
                  />
                )}
              </td>
              <td style={{ padding: '8px 12px', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {t.display_name || <span style={{ color: colors.textSecondary }}>（无）</span>}
              </td>
              <td style={{ padding: '8px 12px', color: colors.textSecondary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {t.comment || '—'}
              </td>
              <td style={{ padding: '8px 12px' }}>{t.column_count}</td>
              <td style={{ padding: '8px 12px', overflow: 'hidden' }}>
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {t.groups.length === 0
                    ? <span style={{ color: colors.textSecondary }}>—</span>
                    : t.groups.map((g) => (
                      <span key={g.id} style={{
                        background: colors.accent + '20', color: colors.accent,
                        borderRadius: radii.sm, padding: '2px 8px', fontSize: 12,
                        whiteSpace: 'nowrap',
                      }}>{g.name}</span>
                    ))}
                </div>
              </td>
              <td style={{ padding: '8px 12px' }}>
                <button
                  onClick={() => openDetail(t.name)}
                  style={{ ...secondaryBtnStyle, padding: '4px 10px', fontSize: 12, whiteSpace: 'nowrap' }}
                >
                  查看字段
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* 删除确认弹窗 */}
      {showDeleteConfirm && (
        <Modal title="确认删除" onClose={() => setShowDeleteConfirm(false)}>
          <p style={{ marginBottom: 16 }}>
            确认删除选中的 <strong>{selectedIds.size}</strong> 张表？<br />
            <span style={{ color: colors.errorColor, fontSize: 13 }}>
              此操作将删除物理表数据、元数据及向量索引，不可恢复。
            </span>
          </p>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <button onClick={() => setShowDeleteConfirm(false)} style={secondaryBtnStyle} disabled={deleting}>取消</button>
            <button onClick={handleDeleteSelected} style={dangerBtnStyle} disabled={deleting}>
              {deleting ? '删除中…' : '确认删除'}
            </button>
          </div>
        </Modal>
      )}

      {/* 弹窗 */}
      {showUpload && (
        <UploadModal
          groups={groups}
          tables={tables}
          onClose={() => setShowUpload(false)}
          onSuccess={handleAfterUpload}
        />
      )}
      {showGroupManage && (
        <GroupManageModal
          tables={tables}
          onClose={() => { setShowGroupManage(false); load().catch(() => {}) }}
        />
      )}
      {detailTarget && (
        <FieldDetailModal
          detail={detailTarget}
          onClose={() => setDetailTarget(null)}
          onEditMeta={(d) => setEditMetaTarget(d)}
          onRefresh={async () => {
            try { setDetailTarget(await TablesAPI.detail(detailTarget.name)) } catch { }
            load().catch(() => {})
          }}
        />
      )}
      {editMetaTarget && (
        <EditTableMetaModal
          detail={editMetaTarget}
          onClose={() => setEditMetaTarget(null)}
          onSuccess={async () => {
            setEditMetaTarget(null)
            try { setDetailTarget(await TablesAPI.detail(editMetaTarget.name)) } catch { }
            load().catch(() => {})
          }}
        />
      )}
    </>
  )
}

// ─────────────────────────────────────────────────────────────────
// 上传弹窗
// ─────────────────────────────────────────────────────────────────

function UploadModal({
  groups, tables, onClose, onSuccess,
}: {
  groups: TableGroup[]
  tables: TableInfo[]
  onClose: () => void
  onSuccess: () => void
}) {
  const fileRef = useRef<HTMLInputElement>(null)
  const { startUpload } = useUploadTasks()
  const [files, setFiles] = useState<File[]>([])
  const [groupId, setGroupId] = useState('')
  const [mode, setMode] = useState<'new' | 'update'>('new')
  const [selectedTableIds, setSelectedTableIds] = useState<Set<string>>(new Set())
  const [updateFiles, setUpdateFiles] = useState<Record<string, File>>({})

  const groupTables = useMemo(
    () => tables.filter((t) => t.groups.some((g) => g.id === groupId)),
    [tables, groupId],
  )

  const groupOptions: SelectOption[] = [
    { value: '', label: '— 请选择分组 —' },
    ...groups.map((g) => ({ value: g.id, label: g.name })),
  ]

  const selectedUpdateTables = useMemo(
    () => groupTables.filter((t) => t.id && selectedTableIds.has(t.id)),
    [groupTables, selectedTableIds],
  )

  const handleModeChange = (nextMode: 'new' | 'update') => {
    setMode(nextMode)
    setSelectedTableIds(new Set())
    setUpdateFiles({})
    setFiles([])
    if (fileRef.current) fileRef.current.value = ''
  }

  const handleFileChange = (selected: FileList | null) => {
    const picked = Array.from(selected || [])
    if (picked.length > MAX_NEW_TABLE_UPLOAD_FILES) {
      alert(`新建表一次最多上传 ${MAX_NEW_TABLE_UPLOAD_FILES} 个文件，已保留前 ${MAX_NEW_TABLE_UPLOAD_FILES} 个`)
    }
    setFiles(picked.slice(0, MAX_NEW_TABLE_UPLOAD_FILES))
  }

  const handleGroupChange = (nextGroupId: string) => {
    setGroupId(nextGroupId)
    setSelectedTableIds(new Set())
    setUpdateFiles({})
  }

  const toggleUpdateTable = (tableId: string) => {
    const next = new Set(selectedTableIds)
    if (next.has(tableId)) {
      next.delete(tableId)
      setUpdateFiles((prev) => {
        const copy = { ...prev }
        delete copy[tableId]
        return copy
      })
    } else {
      if (next.size >= MAX_NEW_TABLE_UPLOAD_FILES) {
        alert(`更新已有表一次最多选择 ${MAX_NEW_TABLE_UPLOAD_FILES} 张表`)
        return
      }
      next.add(tableId)
    }
    setSelectedTableIds(next)
  }

  const setUpdateTableFile = (tableId: string, selected: FileList | null) => {
    const file = selected?.[0]
    if (!file) return
    setUpdateFiles((prev) => ({ ...prev, [tableId]: file }))
  }

  const clearUpdateTableFile = (tableId: string) => {
    setUpdateFiles((prev) => {
      const copy = { ...prev }
      delete copy[tableId]
      return copy
    })
  }

  const handleSubmit = async () => {
    if (!groupId) { alert('请选择分组'); return }
    if (mode === 'update') {
      if (selectedUpdateTables.length === 0) { alert('请选择要更新的表'); return }
      const missing = selectedUpdateTables.find((table) => table.id && !updateFiles[table.id])
      if (missing) {
        alert(`请为「${missing.display_name || missing.comment || missing.name}」选择上传文件`)
        return
      }
      startUpload({
        files: selectedUpdateTables.map((table) => updateFiles[table.id!]),
        groupId,
        targetTableIds: selectedUpdateTables.map((table) => table.id!),
      })
      onSuccess()
      return
    }
    if (files.length === 0) { alert('请选择文件'); return }
    if (mode === 'new' && files.length > MAX_NEW_TABLE_UPLOAD_FILES) {
      alert(`新建表一次最多上传 ${MAX_NEW_TABLE_UPLOAD_FILES} 个文件`)
      return
    }
    startUpload({
      files,
      groupId,
    })
    onSuccess()
  }

  return (
    <Modal title="上传数据文件" onClose={onClose} maxWidth={760} closeOnBackdropClick={false}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* 分组（必选） */}
        <div>
          <label style={labelStyle}>所属分组 <span style={{ color: '#e57575' }}>*</span></label>
          <CustomSelect
            value={groupId}
            onChange={handleGroupChange}
            options={groupOptions}
          />
        </div>

        {/* 上传方式 */}
        <div>
          <label style={labelStyle}>上传方式</label>
          <div style={{ display: 'flex', gap: 10 }}>
            {(['new', 'update'] as const).map((m) => (
              <label key={m} style={{
                flex: 1, display: 'flex', alignItems: 'center', gap: 8,
                cursor: 'pointer', fontSize: 14, fontFamily,
                border: `2px solid ${mode === m ? colors.accent : colors.border}`,
                borderRadius: radii.md,
                padding: '10px 16px',
                background: mode === m ? colors.accent + '08' : 'transparent',
                color: mode === m ? colors.accent : colors.textPrimary,
                fontWeight: mode === m ? 500 : 400,
                transition: 'all 0.15s ease',
                userSelect: 'none',
              }}>
                <input
                  type="radio" name="upload-mode" value={m}
                  checked={mode === m}
                  onChange={() => handleModeChange(m)}
                  style={{ accentColor: colors.accent }}
                />
                {m === 'new' ? '新建表' : '更新已有表'}
              </label>
            ))}
          </div>
        </div>

        {/* 目标表（更新模式） */}
        {mode === 'update' && (
          <div>
            <label style={labelStyle}>
              选择要更新的表 <span style={{ color: '#e57575' }}>*</span>
              <span style={{ color: colors.textSecondary }}>，每张表绑定 1 个文件</span>
            </label>
            {groupTables.length === 0 && groupId && (
              <div style={{ fontSize: 12, color: colors.textSecondary, marginTop: 4 }}>
                该分组下暂无表，请先建表或切换分组
              </div>
            )}
            {!groupId && (
              <div style={{ fontSize: 12, color: colors.textSecondary }}>请先选择分组</div>
            )}
            {groupId && groupTables.length > 0 && (
              <div style={{
                border: `1px solid ${colors.border}`,
                borderRadius: radii.sm,
                overflow: 'hidden',
                maxHeight: 280,
                overflowY: 'auto',
              }}>
                {groupTables.map((table) => {
                  const tableId = table.id || ''
                  const selected = !!table.id && selectedTableIds.has(table.id)
                  const selectedFile = table.id ? updateFiles[table.id] : undefined
                  return (
                    <div key={table.name} style={{
                      display: 'grid',
                      gridTemplateColumns: '28px minmax(0, 1fr) minmax(180px, 240px)',
                      gap: 10,
                      alignItems: 'center',
                      padding: '8px 10px',
                      borderBottom: `1px solid ${colors.borderLight}`,
                      background: selected ? colors.accent + '08' : '#fff',
                    }}>
                      <input
                        type="checkbox"
                        checked={selected}
                        disabled={!table.id}
                        onChange={() => table.id && toggleUpdateTable(table.id)}
                        style={{ accentColor: colors.accent }}
                      />
                      <div style={{ minWidth: 0 }}>
                        <Tooltip content={table.display_name || table.comment || table.name}>
                          <div style={{
                            fontSize: 13,
                            fontWeight: 500,
                            color: colors.textPrimary,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}>
                            {table.display_name || table.comment || table.name}
                          </div>
                        </Tooltip>
                        <Tooltip content={table.name}>
                          <div style={{
                            marginTop: 2,
                            fontSize: 12,
                            color: colors.textSecondary,
                            fontFamily: 'monospace',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}>
                            {table.name}
                          </div>
                        </Tooltip>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 6, minWidth: 0 }}>
                        {selected ? (
                          <>
                            {selectedFile ? (
                              <>
                                <Tooltip content={selectedFile.name}>
                                  <span style={{
                                    minWidth: 0,
                                    flex: '1 1 auto',
                                    fontSize: 12,
                                    color: colors.textPrimary,
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                  }}>
                                    {selectedFile.name}
                                  </span>
                                </Tooltip>
                                {table.id && (
                                  <Tooltip content="清除已选择文件">
                                  <button
                                    type="button"
                                    aria-label="清除已选择文件"
                                    onClick={() => clearUpdateTableFile(table.id!)}
                                    style={{
                                      ...secondaryBtnStyle,
                                      width: 28,
                                      minWidth: 28,
                                      height: 28,
                                      padding: 0,
                                      display: 'inline-flex',
                                      alignItems: 'center',
                                      justifyContent: 'center',
                                    }}
                                  >
                                    <CloseIcon width={13} height={13} color={colors.textSecondary} />
                                  </button>
                                  </Tooltip>
                                )}
                              </>
                            ) : (
                              <label style={{
                                ...secondaryBtnStyle,
                                display: 'inline-flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                height: 30,
                                padding: '0 10px',
                                fontSize: 12,
                                whiteSpace: 'nowrap',
                                cursor: 'pointer',
                              }}>
                                选择文件
                                <input
                                  type="file"
                                  accept=".xlsx,.xls,.csv"
                                  style={{ display: 'none' }}
                                  onChange={(e) => setUpdateTableFile(tableId, e.target.files)}
                                />
                              </label>
                            )}
                          </>
                        ) : (
                          <span style={{ fontSize: 12, color: colors.textSecondary }}>勾选后选择文件</span>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
            <div style={{ fontSize: 12, color: colors.textSecondary, marginTop: 6 }}>
              系统会自动新增多出的字段、保留缺少的字段，只追加新行并跳过重复行。
            </div>
          </div>
        )}

        {/* 文件选择 */}
        {mode === 'new' && <div>
          <label style={labelStyle}>
            数据文件（Excel / CSV）
            {mode === 'new' && <span style={{ color: colors.textSecondary }}>，最多 {MAX_NEW_TABLE_UPLOAD_FILES} 个</span>}
          </label>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              style={secondaryBtnStyle}
            >
              选择文件
            </button>
            <span style={{ fontSize: 13, color: files.length ? colors.textPrimary : colors.textSecondary }}>
              {files.length === 0
                ? '未选择文件'
                : files.length === 1
                  ? files[0].name
                  : `已选择 ${files.length} 个文件`}
            </span>
            <input
              ref={fileRef}
              type="file"
              accept=".xlsx,.xls,.csv"
              multiple
              style={{ display: 'none' }}
              onChange={(e) => handleFileChange(e.target.files)}
            />
          </div>
          {files.length > 1 && (
            <div style={{
              marginTop: 8,
              maxHeight: 120,
              overflowY: 'auto',
              border: `1px solid ${colors.border}`,
              borderRadius: radii.sm,
              padding: '6px 8px',
              fontSize: 12,
              color: colors.textSecondary,
              lineHeight: 1.7,
            }}>
              {files.map((f) => (
                <div key={`${f.name}-${f.size}-${f.lastModified}`} style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {f.name}
                </div>
              ))}
            </div>
          )}
        </div>}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 4 }}>
          <button onClick={onClose} style={secondaryBtnStyle}>取消</button>
          <button onClick={handleSubmit} style={primaryBtnStyle}>
            确认上传
          </button>
        </div>
      </div>
    </Modal>
  )
}

// ─────────────────────────────────────────────────────────────────
// 字段详情弹窗（含行内注释编辑）
// ─────────────────────────────────────────────────────────────────

function FieldDetailModal({
  detail, onClose, onEditMeta, onRefresh,
}: {
  detail: TableDetail
  onClose: () => void
  onEditMeta: (d: TableDetail) => void
  onRefresh: () => void
}) {
  const [editingColId, setEditingColId] = useState<string | null>(null)
  const [editingComment, setEditingComment] = useState('')
  const [saving, setSaving] = useState(false)

  const startEdit = (colId: string, current: string | null) => {
    setEditingColId(colId)
    setEditingComment(current || '')
  }

  const saveComment = async (colId: string) => {
    if (!detail.id) return
    setSaving(true)
    try {
      await TablesAPI.updateColumnComment(detail.id, colId, editingComment)
      setEditingColId(null)
      onRefresh()
    } catch (e: any) {
      alert(e?.response?.data?.detail || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={`字段详情 — ${detail.display_name || detail.name}`} onClose={onClose} maxWidth={720}>
      {/* 表信息摘要 */}
      <div style={{
        background: colors.sidebarBg, borderRadius: radii.md, padding: '10px 14px',
        marginBottom: 14, fontSize: 13, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 16px',
      }}>
        <div><span style={{ color: colors.textSecondary }}>中文表名：</span>{detail.display_name || '—'}</div>
        <div><span style={{ color: colors.textSecondary }}>英文表名：</span><code style={{ fontFamily: 'monospace' }}>{detail.name}</code></div>
        <div><span style={{ color: colors.textSecondary }}>表注释：</span>{detail.comment || '—'}</div>
        <div><span style={{ color: colors.textSecondary }}>所属分组：</span>
          {detail.groups.length === 0 ? '—' : detail.groups.map((g) => g.name).join('、')}
        </div>
      </div>
      <button
        onClick={() => onEditMeta(detail)}
        style={{ ...secondaryBtnStyle, fontSize: 12, marginBottom: 12 }}
      >
        编辑表元数据
      </button>

      {/* 字段表格 */}
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, tableLayout: 'fixed' }}>
        <colgroup>
          <col style={{ width: 220 }} />
          <col />
          <col style={{ width: 90 }} />
        </colgroup>
        <thead>
          <tr style={{ background: colors.sidebarBg }}>
            {['字段名', '中文注释', '操作'].map((h) => (
              <th key={h} style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 600, color: colors.textSecondary, borderBottom: `1px solid ${colors.border}` }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {detail.columns.map((c) => {
            const displayColumnName = c.original_name || c.name
            return (
            <tr key={c.name} style={{ borderBottom: `1px solid ${colors.border}` }}>
              <td style={{ padding: '6px 10px', fontFamily: 'monospace' }}>
                <Tooltip content={
                  c.original_name && c.original_name !== c.name
                    ? <>{`原始列名：${c.original_name}`}<br />{`数据库列名：${c.name}`}</>
                    : c.name
                }>
                  <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {displayColumnName}
                  </div>
                </Tooltip>
              </td>
              <td style={{ padding: '6px 10px' }}>
                {editingColId === c.id ? (
                  <input
                    value={editingComment}
                    onChange={(e) => setEditingComment(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && c.id) saveComment(c.id) }}
                    autoFocus
                    style={{ ...inputStyle, fontSize: 12, padding: '3px 6px', width: '100%' }}
                  />
                ) : (
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}>
                    {c.comment || <span style={{ color: colors.textSecondary }}>—</span>}
                  </span>
                )}
              </td>
              <td style={{ padding: '6px 10px' }}>
                {c.id && (
                  editingColId === c.id ? (
                    <button
                      onClick={() => saveComment(c.id!)}
                      disabled={saving}
                      style={{ ...primaryBtnStyle, fontSize: 11, padding: '3px 8px' }}
                    >保存</button>
                  ) : (
                    <button
                      onClick={() => startEdit(c.id!, c.comment)}
                      style={{ ...secondaryBtnStyle, fontSize: 11, padding: '3px 8px' }}
                    >编辑</button>
                  )
                )}
              </td>
            </tr>
            )
          })}
        </tbody>
      </table>
    </Modal>
  )
}

// ─────────────────────────────────────────────────────────────────
// 编辑表元数据弹窗（中文表名 + 表注释）
// ─────────────────────────────────────────────────────────────────

function EditTableMetaModal({
  detail, onClose, onSuccess,
}: {
  detail: TableDetail
  onClose: () => void
  onSuccess: () => void
}) {
  const [displayName, setDisplayName] = useState(detail.display_name || '')
  const [comment, setComment] = useState(detail.comment || '')
  const [loading, setLoading] = useState(false)

  const save = async () => {
    if (!detail.id) { alert('该表尚未注册到元数据库，无法编辑'); return }
    setLoading(true)
    try {
      await TablesAPI.updateMetadata(detail.id, displayName, comment)
      onSuccess()
    } catch (e: any) {
      alert(e?.response?.data?.detail || '保存失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title="编辑表元数据" onClose={onClose}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div>
          <label style={labelStyle}>中文表名</label>
          <input
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="简洁名词短语，15字以内"
            style={inputStyle}
          />
        </div>
        <div>
          <label style={labelStyle}>表注释</label>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={3}
            placeholder="一句话描述表的用途和存储内容"
            style={{ ...inputStyle, resize: 'vertical', height: 80 }}
          />
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button onClick={onClose} style={secondaryBtnStyle} disabled={loading}>取消</button>
          <button onClick={save} style={primaryBtnStyle} disabled={loading}>
            {loading ? '保存中…' : '保存'}
          </button>
        </div>
      </div>
    </Modal>
  )
}

// ─────────────────────────────────────────────────────────────────
// 分组管理弹窗（整合原 TableGroupsTab 功能）
// ─────────────────────────────────────────────────────────────────

function GroupManageModal({
  tables, onClose,
}: {
  tables: TableInfo[]
  onClose: () => void
}) {
  const [groups, setGroups] = useState<TableGroup[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [addForm, setAddForm] = useState({ name: '', description: '' })
  const [editing, setEditing] = useState<TableGroup | null>(null)
  const [editForm, setEditForm] = useState({ name: '', description: '' })
  const [toDelete, setToDelete] = useState<TableGroup | null>(null)
  const [configuring, setConfiguring] = useState<TableGroup | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [cfgSearch, setCfgSearch] = useState('')

  const loadGroups = async () => setGroups(await TableGroupsAPI.list())
  useEffect(() => { loadGroups().catch(() => {}) }, [])

  const submitAdd = async () => {
    if (!addForm.name.trim()) { alert('请填写分组名称'); return }
    try {
      await TableGroupsAPI.create({ name: addForm.name.trim(), description: addForm.description || undefined })
      setShowAdd(false); setAddForm({ name: '', description: '' })
      await loadGroups()
    } catch (e: any) { alert(e?.response?.data?.detail || '创建失败') }
  }

  const openEdit = (g: TableGroup) => { setEditing(g); setEditForm({ name: g.name, description: g.description || '' }) }
  const submitEdit = async () => {
    if (!editing) return
    try {
      await TableGroupsAPI.update(editing.id, { name: editForm.name, description: editForm.description })
      setEditing(null); await loadGroups()
    } catch (e: any) { alert(e?.response?.data?.detail || '更新失败') }
  }

  const submitDelete = async () => {
    if (!toDelete) return
    try {
      await TableGroupsAPI.remove(toDelete.id)
      setToDelete(null); await loadGroups()
    } catch (e: any) { alert(e?.response?.data?.detail || '删除失败') }
  }

  const openConfigure = async (g: TableGroup) => {
    setConfiguring(g); setCfgSearch('')
    try {
      const current = await TableGroupsAPI.getTables(g.id)
      setSelected(new Set(current.map(keyOf)))
    } catch { setSelected(new Set()) }
  }

  const toggle = (t: TableInfo) => {
    const k = keyOf(t)
    const next = new Set(selected)
    if (next.has(k)) next.delete(k); else next.add(k)
    setSelected(next)
  }

  const filteredCfg = useMemo(() => {
    if (!cfgSearch.trim()) return tables
    const kw = cfgSearch.trim().toLowerCase()
    return tables.filter(
      (t) => t.name.toLowerCase().includes(kw) || (t.display_name || t.comment || '').toLowerCase().includes(kw),
    )
  }, [tables, cfgSearch])

  const groupActionButtonStyle: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: 68,
    minWidth: 68,
    height: 28,
    padding: '0 10px',
    fontSize: 12,
    lineHeight: 1,
    whiteSpace: 'nowrap',
    flex: '0 0 68px',
  }

  const groupActionSlotStyle: CSSProperties = {
    display: 'inline-flex',
    flex: '0 0 68px',
  }

  const saveConfigure = async () => {
    if (!configuring) return
    const tableRefs: TableRef[] = Array.from(selected).map((k) => {
      const [schema, name] = k.split('.')
      return { schema, name }
    })
    try {
      await TableGroupsAPI.setTables(configuring.id, tableRefs)
      setConfiguring(null)
      await loadGroups()
    } catch (e: any) { alert(e?.response?.data?.detail || '保存失败') }
  }

  return (
    <Modal title="管理分组" onClose={onClose} maxWidth={820}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 12 }}>
        <button onClick={() => setShowAdd(true)} style={primaryBtnStyle}>+ 新建分组</button>
        <div style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 1.5 }}>
          被角色引用的分组需先到「角色权限」取消引用后才能删除。
        </div>
      </div>

      <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', minWidth: 760, borderCollapse: 'collapse', fontSize: 13, tableLayout: 'fixed' }}>
        <colgroup>
          <col style={{ width: 140 }} />
          <col />
          <col style={{ width: 70 }} />
          <col style={{ width: 95 }} />
          <col style={{ width: 244 }} />
        </colgroup>
        <thead>
          <tr style={{ background: colors.sidebarBg }}>
            {['分组名', '描述', '包含表数', '角色引用', '操作'].map((h) => (
              <th key={h} style={{ padding: '7px 12px', textAlign: 'left', fontWeight: 600, color: colors.textSecondary, borderBottom: `1px solid ${colors.border}` }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {groups.length === 0 && (
          <tr><td colSpan={5} style={{ padding: 24, textAlign: 'center', color: colors.textSecondary }}>暂无分组</td></tr>
          )}
          {groups.map((g) => {
            const deleteBlocked = g.role_count > 0
            return (
              <tr key={g.id} style={{ borderBottom: `1px solid ${colors.border}` }}>
                <td style={{ padding: '7px 12px', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{g.name}</td>
                <td style={{ padding: '7px 12px', color: colors.textSecondary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{g.description || '—'}</td>
                <td style={{ padding: '7px 12px' }}>{g.table_count}</td>
                <td style={{ padding: '7px 12px' }}>
                  <span style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    height: 22,
                    padding: '0 8px',
                    borderRadius: radii.sm,
                    background: deleteBlocked ? '#fff7ed' : colors.sidebarBg,
                    color: deleteBlocked ? '#c2410c' : colors.textSecondary,
                    fontWeight: deleteBlocked ? 600 : 400,
                  }}>
                    {g.role_count}
                  </span>
                </td>
                <td style={{ padding: '7px 12px' }}>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button onClick={() => openConfigure(g)} style={{ ...secondaryBtnStyle, ...groupActionButtonStyle }}>配置表</button>
                    <button onClick={() => openEdit(g)} style={{ ...secondaryBtnStyle, ...groupActionButtonStyle }}>编辑</button>
                    <Tooltip content={deleteBlocked ? `该分组正被 ${g.role_count} 个角色引用，请先到「角色权限」取消引用` : '删除分组'}>
                    <span
                      style={groupActionSlotStyle}
                    >
                      <button
                        onClick={() => setToDelete(g)}
                        disabled={deleteBlocked}
                        style={{
                          ...dangerBtnStyle,
                          ...groupActionButtonStyle,
                          opacity: deleteBlocked ? 0.5 : 1,
                          cursor: deleteBlocked ? 'not-allowed' : 'pointer',
                          background: deleteBlocked ? colors.border : colors.errorColor,
                          color: deleteBlocked ? colors.textSecondary : '#fff',
                        }}
                      >
                        {deleteBlocked ? '先解绑' : '删除'}
                      </button>
                    </span>
                    </Tooltip>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      </div>

      {/* 新建分组 */}
      {showAdd && (
        <Modal title="新建分组" onClose={() => setShowAdd(false)}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div><label style={labelStyle}>分组名称</label>
              <input value={addForm.name} onChange={(e) => setAddForm({ ...addForm, name: e.target.value })} style={inputStyle} />
            </div>
            <div><label style={labelStyle}>描述（可选）</label>
              <input value={addForm.description} onChange={(e) => setAddForm({ ...addForm, description: e.target.value })} style={inputStyle} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button onClick={() => setShowAdd(false)} style={secondaryBtnStyle}>取消</button>
              <button onClick={submitAdd} style={primaryBtnStyle}>创建</button>
            </div>
          </div>
        </Modal>
      )}

      {/* 编辑分组 */}
      {editing && (
        <Modal title="编辑分组" onClose={() => setEditing(null)}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div><label style={labelStyle}>分组名称</label>
              <input value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} style={inputStyle} />
            </div>
            <div><label style={labelStyle}>描述</label>
              <input value={editForm.description} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })} style={inputStyle} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button onClick={() => setEditing(null)} style={secondaryBtnStyle}>取消</button>
              <button onClick={submitEdit} style={primaryBtnStyle}>保存</button>
            </div>
          </div>
        </Modal>
      )}

      {/* 删除确认 */}
      {toDelete && (
        <Modal title="确认删除" onClose={() => setToDelete(null)}>
          <p style={{ marginBottom: 16 }}>确认删除分组「{toDelete.name}」？该操作不可恢复。</p>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <button onClick={() => setToDelete(null)} style={secondaryBtnStyle}>取消</button>
            <button onClick={submitDelete} style={dangerBtnStyle}>确认删除</button>
          </div>
        </Modal>
      )}

      {/* 配置包含的表 */}
      {configuring && (
        <Modal title={`配置「${configuring.name}」包含的表`} onClose={() => setConfiguring(null)} maxWidth={720}>
          <input
            value={cfgSearch}
            onChange={(e) => setCfgSearch(e.target.value)}
            placeholder="搜索表名…"
            style={{ ...inputStyle, marginBottom: 10 }}
          />
          <div style={{ maxHeight: 320, overflowY: 'auto', border: `1px solid ${colors.border}`, borderRadius: radii.sm }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, tableLayout: 'fixed' }}>
              <colgroup>
                <col style={{ width: 36 }} />
                <col style={{ width: 140 }} />
                <col />
                <col style={{ width: 60 }} />
              </colgroup>
              <thead style={{ position: 'sticky', top: 0, background: colors.sidebarBg }}>
                <tr>
                  <th style={{ width: 36, padding: '6px 10px' }}>
                    <input type="checkbox"
                      checked={filteredCfg.every((t) => selected.has(keyOf(t)))}
                      onChange={(e) => {
                        const next = new Set(selected)
                        filteredCfg.forEach((t) => e.target.checked ? next.add(keyOf(t)) : next.delete(keyOf(t)))
                        setSelected(next)
                      }}
                    />
                  </th>
                  {['中文表名', '英文表名', '字段数'].map((h) => (
                    <th key={h} style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 600, color: colors.textSecondary }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredCfg.map((t) => (
                  <tr key={t.name} onClick={() => toggle(t)} style={{ cursor: 'pointer', borderBottom: `1px solid ${colors.border}` }}>
                    <td style={{ padding: '5px 10px' }}>
                      <input type="checkbox" readOnly checked={selected.has(keyOf(t))} />
                    </td>
                    <td style={{ padding: '5px 10px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.display_name || t.comment || '—'}</td>
                    <td style={{ padding: '5px 10px', fontFamily: 'monospace', color: colors.textSecondary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.name}</td>
                    <td style={{ padding: '5px 10px' }}>{t.column_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
            <button onClick={() => setConfiguring(null)} style={secondaryBtnStyle}>取消</button>
            <button onClick={saveConfigure} style={primaryBtnStyle}>保存</button>
          </div>
        </Modal>
      )}
    </Modal>
  )
}
