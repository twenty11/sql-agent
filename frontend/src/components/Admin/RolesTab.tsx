import React, { useEffect, useMemo, useState } from 'react'
import { colors, radii, fontFamily } from '../../styles/tokens'
import { RolesAPI, TableGroupsAPI } from '../../services/admin'
import type { Role, TableGroup } from '../../types/admin'
import {
  Modal,
  inputStyle, labelStyle,
  primaryBtnStyle, secondaryBtnStyle, dangerBtnStyle,
} from './shared'
import { Tooltip } from '../ui/Tooltip'

export function RolesTab() {
  const [roles, setRoles] = useState<Role[]>([])
  const [groups, setGroups] = useState<TableGroup[]>([])

  const [showAdd, setShowAdd] = useState(false)
  const [addForm, setAddForm] = useState({ name: '', description: '' })

  const [editing, setEditing] = useState<Role | null>(null)
  const [editForm, setEditForm] = useState({ name: '', description: '' })

  const [permEditing, setPermEditing] = useState<Role | null>(null)
  const [permSelected, setPermSelected] = useState<Set<string>>(new Set())
  const [permSearch, setPermSearch] = useState('')

  const [toDelete, setToDelete] = useState<Role | null>(null)

  const loadRoles = async () => setRoles(await RolesAPI.list())
  const loadGroups = async () => setGroups(await TableGroupsAPI.list())

  useEffect(() => {
    loadRoles()
    loadGroups().catch(() => setGroups([]))
  }, [])

  // ── 新建 ──
  const submitAdd = async () => {
    if (!addForm.name.trim()) { alert('请填写角色名'); return }
    try {
      await RolesAPI.create({
        name: addForm.name.trim(),
        description: addForm.description || undefined,
      })
      setShowAdd(false)
      setAddForm({ name: '', description: '' })
      await loadRoles()
    } catch (e: any) {
      alert(e?.response?.data?.detail || '创建角色失败')
    }
  }

  // ── 编辑基本信息 ──
  const openEdit = (r: Role) => {
    setEditing(r)
    setEditForm({ name: r.name, description: r.description || '' })
  }
  const submitEdit = async () => {
    if (!editing) return
    try {
      await RolesAPI.update(editing.id, {
        name: editForm.name !== editing.name ? editForm.name : undefined,
        description: editForm.description,
      })
      setEditing(null)
      await loadRoles()
    } catch (e: any) {
      alert(e?.response?.data?.detail || '更新角色失败')
    }
  }

  // ── 删除 ──
  const submitDelete = async () => {
    if (!toDelete) return
    try {
      await RolesAPI.remove(toDelete.id)
      setToDelete(null)
      await loadRoles()
    } catch (e: any) {
      alert(e?.response?.data?.detail || '删除角色失败')
    }
  }

  // ── 分组权限配置 ──
  const openPerm = async (r: Role) => {
    setPermEditing(r)
    setPermSearch('')
    try {
      const current = await RolesAPI.getGroups(r.id)
      setPermSelected(new Set(current.map((g) => g.id)))
    } catch {
      setPermSelected(new Set())
    }
  }
  const togglePerm = (id: string) => {
    const next = new Set(permSelected)
    if (next.has(id)) next.delete(id); else next.add(id)
    setPermSelected(next)
  }
  const selectAllFiltered = () => {
    const next = new Set(permSelected)
    filteredGroups.forEach((g) => next.add(g.id))
    setPermSelected(next)
  }
  const clearAllFiltered = () => {
    const next = new Set(permSelected)
    filteredGroups.forEach((g) => next.delete(g.id))
    setPermSelected(next)
  }
  const submitPerm = async () => {
    if (!permEditing) return
    try {
      await RolesAPI.setGroups(permEditing.id, Array.from(permSelected))
      setPermEditing(null)
      await loadRoles()
    } catch (e: any) {
      alert(e?.response?.data?.detail || '保存失败')
    }
  }

  const filteredGroups = useMemo(() => {
    if (!permSearch) return groups
    const kw = permSearch.toLowerCase()
    return groups.filter(
      (g) =>
        g.name.toLowerCase().includes(kw) ||
        (g.description || '').toLowerCase().includes(kw),
    )
  }, [groups, permSearch])

  return (
    <>
      <div style={{
        display: 'flex', marginBottom: 16,
        alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ fontSize: 14, color: colors.textSecondary }}>
          共 {roles.length} 个角色 · {groups.length} 个表分组可供配置
        </div>
        <button onClick={() => setShowAdd(true)} style={primaryBtnStyle}>新建角色</button>
      </div>

      <div style={{
        background: '#fff',
        borderRadius: radii.xxl,
        border: `1px solid ${colors.border}`,
        overflow: 'hidden',
      }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, fontFamily, tableLayout: 'fixed' }}>
          <colgroup>
            <col style={{ width: 140 }} />
            <col />
            <col style={{ width: 175 }} />
            <col style={{ width: 90 }} />
            <col style={{ width: 200 }} />
          </colgroup>
          <thead>
            <tr style={{ background: colors.tableHeadBg }}>
              {['角色名', '描述', '可访问表分组', '用户数', '操作'].map((h) => (
                <th key={h} style={{
                  padding: '10px 16px', textAlign: 'left',
                  fontSize: 13, fontWeight: 600, color: colors.textSecondary,
                  borderBottom: `1px solid ${colors.border}`,
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {roles.map((r) => (
              <tr key={r.id} style={{ borderBottom: `1px solid rgba(0,0,0,0.05)` }}>
                <td style={{ padding: '10px 16px', fontWeight: 600 }}>{r.name}</td>
                <td style={{ padding: '10px 16px', color: colors.textSecondary }}>
                  {r.description || '—'}
                </td>
                <td style={{ padding: '10px 16px', color: colors.textSecondary }}>
                  {r.name === 'admin'
                    ? <span style={{ color: colors.accent, fontWeight: 500 }}>全部表（不受限）</span>
                    : `${r.group_count} 个分组`}
                </td>
                <td style={{ padding: '10px 16px', color: colors.textSecondary }}>{r.user_count}</td>
                <td style={{ padding: '10px 16px', display: 'flex', gap: 6, alignItems: 'center' }}>
                  <Tooltip content={r.name === 'admin' ? 'admin 不受表级权限限制' : undefined}>
                    <button
                      onClick={() => openPerm(r)}
                      disabled={r.name === 'admin'}
                      style={{
                        border: `1px solid ${colors.border}`,
                        background: 'transparent', borderRadius: radii.sm,
                        padding: '3px 8px', fontSize: 13,
                        cursor: r.name === 'admin' ? 'not-allowed' : 'pointer',
                        color: r.name === 'admin' ? colors.textMuted : colors.accent,
                        fontFamily, whiteSpace: 'nowrap', flexShrink: 0,
                      }}
                    >
                      配置分组
                    </button>
                  </Tooltip>
                  <button onClick={() => openEdit(r)} style={{
                    border: `1px solid ${colors.border}`, background: 'transparent',
                    borderRadius: radii.sm, padding: '3px 8px', fontSize: 13,
                    cursor: 'pointer', color: colors.textSecondary, fontFamily,
                    whiteSpace: 'nowrap', flexShrink: 0,
                  }}>
                    编辑
                  </button>
                  <Tooltip content={r.is_builtin ? '内置角色不可删除' : undefined}>
                    <button
                      onClick={() => setToDelete(r)}
                      disabled={r.is_builtin}
                      style={{
                        border: `1px solid ${colors.border}`, background: 'transparent',
                        borderRadius: radii.sm, padding: '3px 8px', fontSize: 13,
                        cursor: r.is_builtin ? 'not-allowed' : 'pointer',
                        color: r.is_builtin ? colors.textMuted : colors.errorColor,
                        fontFamily, whiteSpace: 'nowrap', flexShrink: 0,
                      }}
                    >
                      删除
                    </button>
                  </Tooltip>
                </td>
              </tr>
            ))}
            {roles.length === 0 && (
              <tr>
                <td colSpan={5} style={{
                  padding: '40px 16px', textAlign: 'center', color: colors.textMuted,
                }}>
                  暂无角色
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* 新建角色 */}
      {showAdd && (
        <Modal title="新建角色" onClose={() => setShowAdd(false)} maxWidth={420}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div>
              <label style={labelStyle}>角色名 * (英文标识，唯一)</label>
              <input
                style={inputStyle}
                value={addForm.name}
                onChange={(e) => setAddForm({ ...addForm, name: e.target.value })}
                placeholder="如 finance_reader"
              />
            </div>
            <div>
              <label style={labelStyle}>描述</label>
              <input
                style={inputStyle}
                value={addForm.description}
                onChange={(e) => setAddForm({ ...addForm, description: e.target.value })}
                placeholder="财务只读"
              />
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20 }}>
            <button onClick={() => setShowAdd(false)} style={secondaryBtnStyle}>取消</button>
            <button onClick={submitAdd} style={primaryBtnStyle}>创建</button>
          </div>
        </Modal>
      )}

      {/* 编辑角色 */}
      {editing && (
        <Modal title={`编辑角色 — ${editing.name}`} onClose={() => setEditing(null)} maxWidth={420}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div>
              <label style={labelStyle}>角色名{editing.is_builtin && ' (内置角色不可修改)'}</label>
              <input
                style={{ ...inputStyle, background: editing.is_builtin ? colors.hoverBg : colors.inputBg }}
                value={editForm.name}
                disabled={editing.is_builtin}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
              />
            </div>
            <div>
              <label style={labelStyle}>描述</label>
              <input
                style={inputStyle}
                value={editForm.description}
                onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
              />
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20 }}>
            <button onClick={() => setEditing(null)} style={secondaryBtnStyle}>取消</button>
            <button onClick={submitEdit} style={primaryBtnStyle}>保存</button>
          </div>
        </Modal>
      )}

      {/* 删除确认 */}
      {toDelete && (
        <Modal title="确认删除角色？" onClose={() => setToDelete(null)} maxWidth={380}>
          <div style={{ fontSize: 14, color: colors.textSecondary, marginBottom: 20 }}>
            即将删除角色 <strong>{toDelete.name}</strong>
            {toDelete.user_count > 0 && `（当前绑定 ${toDelete.user_count} 个用户）`}
            ，此操作不可恢复。
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
            <button onClick={() => setToDelete(null)} style={secondaryBtnStyle}>取消</button>
            <button onClick={submitDelete} style={dangerBtnStyle}>确认删除</button>
          </div>
        </Modal>
      )}

      {/* 表分组权限配置 */}
      {permEditing && (
        <Modal
          title={`配置可访问表分组 — ${permEditing.name}`}
          onClose={() => setPermEditing(null)}
          maxWidth={640}
        >
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            marginBottom: 12,
          }}>
            <input
              placeholder="按分组名或描述搜索…"
              value={permSearch}
              onChange={(e) => setPermSearch(e.target.value)}
              style={{ ...inputStyle, flex: 1 }}
            />
            <button onClick={selectAllFiltered} style={secondaryBtnStyle}>全选</button>
            <button onClick={clearAllFiltered} style={secondaryBtnStyle}>全不选</button>
          </div>
          <div style={{ fontSize: 13, color: colors.textMuted, marginBottom: 8 }}>
            已选 <strong>{permSelected.size}</strong> / {groups.length} 个分组
            {permSelected.size === 0 && (
              <span style={{ marginLeft: 8, color: colors.errorColor }}>
                ⚠ 不配置任何分组意味着该角色的用户无法访问任何表
              </span>
            )}
          </div>
          <div style={{
            border: `1px solid ${colors.border}`,
            borderRadius: radii.sm,
            maxHeight: 400, overflow: 'auto',
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, fontFamily }}>
              <thead style={{ position: 'sticky', top: 0, background: colors.tableHeadBg }}>
                <tr>
                  <th style={{ padding: '8px 12px', width: 40 }}></th>
                  <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 13, color: colors.textSecondary }}>
                    分组名
                  </th>
                  <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 13, color: colors.textSecondary }}>
                    描述
                  </th>
                  <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 13, color: colors.textSecondary, width: 80 }}>
                    包含表数
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredGroups.map((g) => (
                  <tr
                    key={g.id}
                    onClick={() => togglePerm(g.id)}
                    style={{
                      borderBottom: `1px solid rgba(0,0,0,0.05)`,
                      cursor: 'pointer',
                      background: permSelected.has(g.id) ? 'rgba(0,117,222,0.04)' : 'transparent',
                    }}
                  >
                    <td style={{ padding: '8px 12px' }}>
                      <input
                        type="checkbox"
                        checked={permSelected.has(g.id)}
                        onChange={() => togglePerm(g.id)}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </td>
                    <td style={{ padding: '8px 12px', fontWeight: 500 }}>{g.name}</td>
                    <td style={{ padding: '8px 12px', color: colors.textSecondary }}>
                      {g.description || '—'}
                    </td>
                    <td style={{ padding: '8px 12px', color: colors.textMuted }}>
                      {g.table_count}
                    </td>
                  </tr>
                ))}
                {filteredGroups.length === 0 && (
                  <tr>
                    <td colSpan={4} style={{
                      padding: '30px 12px', textAlign: 'center', color: colors.textMuted,
                    }}>
                      {groups.length === 0 ? '还没有表分组，请先到"表分组"页面创建' : '没有匹配的分组'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 16 }}>
            <button onClick={() => setPermEditing(null)} style={secondaryBtnStyle}>取消</button>
            <button onClick={submitPerm} style={primaryBtnStyle}>保存权限</button>
          </div>
        </Modal>
      )}
    </>
  )
}
