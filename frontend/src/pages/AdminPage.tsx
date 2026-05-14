import React, { useState } from 'react'
import { AppSideLayout, type SideTab } from '../components/Layout/AppSideLayout'
import { UsersTab } from '../components/Admin/UsersTab'
import { RolesTab } from '../components/Admin/RolesTab'
import { TablesTab } from '../components/Admin/TablesTab'
import { VectorstoreTab } from '../components/Admin/VectorstoreTab'
import { UploadTaskDock } from '../components/Admin/UploadTaskDock'

type Tab = 'users' | 'roles' | 'tables' | 'vectorstore'

const TABS: SideTab<Tab>[] = [
  { key: 'users', label: '用户管理' },
  { key: 'roles', label: '角色权限' },
  { key: 'tables', label: '表与分组' },
  { key: 'vectorstore', label: '向量同步' },
]

const TAB_TITLES: Record<Tab, string> = {
  users: '用户管理',
  roles: '角色与分组权限',
  tables: '表与分组',
  vectorstore: '向量库同步',
}

export function AdminPage() {
  const [tab, setTab] = useState<Tab>('users')

  return (
    <AppSideLayout<Tab>
      tabs={TABS}
      activeTab={tab}
      onChangeTab={setTab}
      title={TAB_TITLES[tab]}
    >
      {tab === 'users' && <UsersTab />}
      {tab === 'roles' && <RolesTab />}
      {tab === 'tables' && <TablesTab />}
      {tab === 'vectorstore' && <VectorstoreTab />}
      {tab === 'tables' && <UploadTaskDock />}
    </AppSideLayout>
  )
}
