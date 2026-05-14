import React, { useEffect, useMemo, useState } from 'react'
import { colors, radii, fontFamily } from '../../styles/tokens'
import { RolesAPI, UsersAPI } from '../../services/admin'
import type { Role, UserItem } from '../../types/admin'
import {
  Modal, CustomSelect, RoleBadge, StatusBadge, ToggleSwitch,
  inputStyle, labelStyle,
  primaryBtnStyle, secondaryBtnStyle, dangerBtnStyle,
} from './shared'
import { ConfirmDialog } from '../ui/ConfirmDialog'

const errorDetail = (e: any, fallback: string) => e?.response?.data?.detail || fallback

export function UsersTab() {
  const [users, setUsers] = useState<UserItem[]>([])
  const [roles, setRoles] = useState<Role[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [filterText, setFilterText] = useState('')
  const [filterRole, setFilterRole] = useState('全部')
  const [filterActive, setFilterActive] = useState('全部')

  const [showAdd, setShowAdd] = useState(false)
  const [addForm, setAddForm] = useState({
    email: '', password: '', full_name: '', roles: ['viewer'],
  })

  const [editingUser, setEditingUser] = useState<UserItem | null>(null)
  const [editRoles, setEditRoles] = useState<string[]>([])

  const [userToDelete, setUserToDelete] = useState<UserItem | null>(null)
  const [userToDisable, setUserToDisable] = useState<UserItem | null>(null)
  const [busyUserId, setBusyUserId] = useState<string | null>(null)
  const [savingAdd, setSavingAdd] = useState(false)
  const [savingEdit, setSavingEdit] = useState(false)
  const [deletingUser, setDeletingUser] = useState(false)

  const load = async () => {
    setLoading(true)
    setLoadError('')
    try {
      const [u, r] = await Promise.all([UsersAPI.list(), RolesAPI.list()])
      setUsers(u); setRoles(r)
    } catch (e: any) {
      const message = errorDetail(e, '加载用户列表失败')
      setLoadError(message)
      alert(message)
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { void load() }, [])

  const performToggleActive = async (u: UserItem, nextActive: boolean) => {
    if (busyUserId) return
    setBusyUserId(u.id)
    try {
      const updated = await UsersAPI.toggleActive(u.id, nextActive)
      setUsers((prev) => prev.map((x) => (x.id === u.id ? updated : x)))
    } catch (e: any) {
      alert(errorDetail(e, '状态更新失败，请稍后重试'))
    } finally {
      setBusyUserId(null)
    }
  }

  const handleToggleActive = (u: UserItem) => {
    if (u.is_active) {
      // 即将禁用，需要确认
      setUserToDisable(u)
    } else {
      performToggleActive(u, true)
    }
  }

  const submitAdd = async () => {
    if (!addForm.email || !addForm.password) {
      alert('请填写邮箱和密码'); return
    }
    setSavingAdd(true)
    try {
      await UsersAPI.create(addForm)
      setShowAdd(false)
      setAddForm({ email: '', password: '', full_name: '', roles: ['viewer'] })
      await load()
    } catch (e: any) {
      alert(errorDetail(e, '添加用户失败，请检查输入或邮箱是否已存在'))
    } finally {
      setSavingAdd(false)
    }
  }

  const openEdit = (u: UserItem) => {
    setEditingUser(u)
    setEditRoles(u.roles)
  }
  const submitEdit = async () => {
    if (!editingUser) return
    setSavingEdit(true)
    try {
      const updated = await UsersAPI.setRoles(editingUser.id, editRoles)
      setUsers((prev) => prev.map((x) => (x.id === updated.id ? updated : x)))
      setEditingUser(null)
    } catch (e: any) {
      alert(errorDetail(e, '保存用户角色失败'))
    } finally {
      setSavingEdit(false)
    }
  }

  const submitDelete = async () => {
    if (!userToDelete) return
    setDeletingUser(true)
    try {
      await UsersAPI.remove(userToDelete.id)
      setUsers((prev) => prev.filter((u) => u.id !== userToDelete.id))
      setUserToDelete(null)
    } catch (e: any) {
      alert(errorDetail(e, '删除用户失败'))
    } finally {
      setDeletingUser(false)
    }
  }

  const filtered = useMemo(() => users.filter((u) => {
    const matchText =
      !filterText ||
      u.email.includes(filterText) ||
      (u.full_name || '').includes(filterText)
    const matchRole = filterRole === '全部' || u.roles.includes(filterRole)
    const matchActive =
      filterActive === '全部' ||
      (filterActive === '已启用' && u.is_active) ||
      (filterActive === '已禁用' && !u.is_active)
    return matchText && matchRole && matchActive
  }), [users, filterText, filterRole, filterActive])

  const smallInput: React.CSSProperties = {
    padding: '7px 12px',
    border: `1px solid ${colors.borderInput}`,
    borderRadius: radii.sm,
    fontSize: 14, fontFamily,
    color: colors.textPrimary,
    background: colors.inputBg,
  }

  return (
    <>
      <div style={{
        display: 'flex', gap: 10, marginBottom: 16,
        flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            placeholder="搜索用户名或邮箱…"
            style={{ ...smallInput, width: 260 }}
          />
          <CustomSelect
            value={filterRole}
            onChange={setFilterRole}
            options={[
              { value: '全部', label: '全部角色' },
              ...roles.map((r) => ({ value: r.name, label: r.name })),
            ]}
            style={{ width: 120 }}
          />
          <CustomSelect
            value={filterActive}
            onChange={setFilterActive}
            options={[
              { value: '全部', label: '全部状态' },
              { value: '已启用', label: '已启用' },
              { value: '已禁用', label: '已禁用' },
            ]}
            style={{ width: 110 }}
          />
        </div>
        <button
          onClick={() => setShowAdd(true)}
          disabled={loading || savingAdd}
          style={{ ...primaryBtnStyle, opacity: loading || savingAdd ? 0.6 : 1 }}
        >
          添加用户
        </button>
      </div>

      <div style={{
        background: '#fff',
        borderRadius: radii.xxl,
        border: `1px solid ${colors.border}`,
        overflow: 'hidden',
      }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, fontFamily, tableLayout: 'fixed' }}>
          <colgroup>
            <col style={{ width: 120 }} />
            <col />
            <col style={{ width: 130 }} />
            <col style={{ width: 90 }} />
            <col style={{ width: 145 }} />
            <col style={{ width: 155 }} />
          </colgroup>
          <thead>
            <tr style={{ background: colors.tableHeadBg }}>
              {['用户', '邮箱', '角色', '状态', '创建时间', '操作'].map((h) => (
                <th key={h} style={{
                  padding: '12px 16px', textAlign: 'left',
                  fontSize: 13, fontWeight: 600, color: colors.textSecondary,
                  borderBottom: `1px solid ${colors.border}`,
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((u) => (
              <tr key={u.id} style={{ borderBottom: `1px solid rgba(0,0,0,0.05)` }}>
                <td style={{ padding: '12px 16px', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{u.full_name || '-'}</td>
                <td style={{ padding: '12px 16px', color: colors.textSecondary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{u.email}</td>
                <td style={{ padding: '12px 16px' }}>
                  {u.roles.length === 0
                    ? <span style={{ color: colors.textMuted, fontSize: 13 }}>未分配</span>
                    : u.roles.map((r) => <RoleBadge key={r} role={r} />)}
                </td>
                <td style={{ padding: '12px 16px' }}>
                  <ToggleSwitch
                    on={u.is_active}
                    onClick={() => handleToggleActive(u)}
                    disabled={busyUserId === u.id}
                  />
                </td>
                <td style={{
                  padding: '12px 16px', color: colors.textMuted, fontSize: 13, whiteSpace: 'nowrap',
                }}>
                  {new Date(u.created_at).toLocaleString('zh-CN').slice(0, 15)}
                </td>
                <td style={{ padding: '12px 16px', display: 'flex', gap: 8, alignItems: 'center' }}>
                  <button disabled={busyUserId === u.id || savingEdit} onClick={() => openEdit(u)} style={{
                    border: `1px solid ${colors.border}`, background: 'transparent',
                    borderRadius: radii.sm, padding: '4px 10px', fontSize: 13,
                    cursor: busyUserId === u.id || savingEdit ? 'not-allowed' : 'pointer',
                    color: colors.textSecondary, fontFamily,
                    whiteSpace: 'nowrap', flexShrink: 0,
                    opacity: busyUserId === u.id || savingEdit ? 0.55 : 1,
                  }}>
                    编辑角色
                  </button>
                  <button disabled={busyUserId === u.id || deletingUser} onClick={() => setUserToDelete(u)} style={{
                    border: `1px solid ${colors.border}`, background: 'transparent',
                    borderRadius: radii.sm, padding: '4px 10px', fontSize: 13,
                    cursor: busyUserId === u.id || deletingUser ? 'not-allowed' : 'pointer',
                    color: colors.errorColor, fontFamily,
                    whiteSpace: 'nowrap', flexShrink: 0,
                    opacity: busyUserId === u.id || deletingUser ? 0.55 : 1,
                  }}>
                    删除
                  </button>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} style={{
                  padding: '40px 16px', textAlign: 'center', color: colors.textMuted,
                }}>
                  {loading ? '加载中…' : loadError || '暂无数据'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* 添加用户 */}
      {showAdd && (
        <Modal title="添加用户" onClose={() => setShowAdd(false)} maxWidth={420}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div>
              <label style={labelStyle}>邮箱 *</label>
              <input
                type="email" style={inputStyle}
                value={addForm.email}
                onChange={(e) => setAddForm({ ...addForm, email: e.target.value })}
              />
            </div>
            <div>
              <label style={labelStyle}>密码 * (至少 6 位)</label>
              <input
                type="password" style={inputStyle}
                value={addForm.password}
                onChange={(e) => setAddForm({ ...addForm, password: e.target.value })}
              />
            </div>
            <div>
              <label style={labelStyle}>姓名</label>
              <input
                type="text" style={inputStyle}
                value={addForm.full_name}
                onChange={(e) => setAddForm({ ...addForm, full_name: e.target.value })}
              />
            </div>
            <div>
              <label style={labelStyle}>角色 (可多选)</label>
              <RoleCheckboxGroup
                roles={roles}
                selected={addForm.roles}
                onChange={(roles) => setAddForm({ ...addForm, roles })}
              />
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20 }}>
            <button onClick={() => setShowAdd(false)} style={secondaryBtnStyle} disabled={savingAdd}>取消</button>
            <button onClick={submitAdd} style={primaryBtnStyle} disabled={savingAdd}>
              {savingAdd ? '添加中…' : '确认添加'}
            </button>
          </div>
        </Modal>
      )}

      {/* 编辑用户角色 */}
      {editingUser && (
        <Modal
          title={`编辑角色 — ${editingUser.full_name || editingUser.email}`}
          onClose={() => setEditingUser(null)}
          maxWidth={420}
        >
          <RoleCheckboxGroup
            roles={roles}
            selected={editRoles}
            onChange={setEditRoles}
          />
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20 }}>
            <button onClick={() => setEditingUser(null)} style={secondaryBtnStyle} disabled={savingEdit}>取消</button>
            <button onClick={submitEdit} style={primaryBtnStyle} disabled={savingEdit}>
              {savingEdit ? '保存中…' : '保存'}
            </button>
          </div>
        </Modal>
      )}

      {/* 删除确认 */}
      {userToDelete && (
        <Modal title="确认删除用户？" onClose={() => setUserToDelete(null)} maxWidth={380}>
          <div style={{ fontSize: 14, color: colors.textSecondary, marginBottom: 20 }}>
            即将删除用户 <strong>{userToDelete.full_name || userToDelete.email}</strong>，此操作不可恢复。
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
            <button onClick={() => setUserToDelete(null)} style={secondaryBtnStyle} disabled={deletingUser}>取消</button>
            <button onClick={submitDelete} style={dangerBtnStyle} disabled={deletingUser}>
              {deletingUser ? '删除中…' : '确认删除'}
            </button>
          </div>
        </Modal>
      )}

      {/* 禁用确认 */}
      <ConfirmDialog
        open={!!userToDisable}
        title="确认禁用该用户？"
        message={`禁用后 ${userToDisable?.full_name || userToDisable?.email || ''} 将无法登录系统，已登录的会话会在 Token 过期后失效。`}
        confirmText="确认禁用"
        cancelText="取消"
        onConfirm={() => {
          if (userToDisable) performToggleActive(userToDisable, false)
          setUserToDisable(null)
        }}
        onCancel={() => setUserToDisable(null)}
      />
    </>
  )
}

function RoleCheckboxGroup({
  roles, selected, onChange,
}: {
  roles: Role[]
  selected: string[]
  onChange: (roles: string[]) => void
}) {
  const toggle = (name: string) => {
    onChange(selected.includes(name)
      ? selected.filter((r) => r !== name)
      : [...selected, name])
  }
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 8,
      border: `1px solid ${colors.border}`, borderRadius: radii.sm,
      padding: 12, maxHeight: 260, overflow: 'auto',
    }}>
      {roles.map((r) => (
        <label key={r.id} style={{
          display: 'flex', alignItems: 'center', gap: 8,
          fontSize: 14, cursor: 'pointer',
        }}>
          <input
            type="checkbox"
            checked={selected.includes(r.name)}
            onChange={() => toggle(r.name)}
          />
          <span style={{ fontWeight: 500, color: colors.textPrimary }}>{r.name}</span>
          {r.description && (
            <span style={{ color: colors.textMuted, fontSize: 13 }}>— {r.description}</span>
          )}
        </label>
      ))}
      {roles.length === 0 && (
        <span style={{ fontSize: 14, color: colors.textMuted }}>暂无角色，请先在「角色管理」中创建</span>
      )}
    </div>
  )
}
