import React, { useState, useEffect } from 'react'
import { fontFamily } from '../styles/tokens'
import { useAuth } from '../hooks/useAuth'
import { useChat } from '../hooks/useChat'
import { Sidebar } from '../components/Layout/Sidebar'
import { ChatArea } from '../components/Layout/ChatArea'
import { SettingsPanel } from '../components/Settings/SettingsPanel'

export function ChatPage() {
  const { user, logout } = useAuth()
  const chat = useChat()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [settingsOpen, setSettingsOpen] = useState(false)

  useEffect(() => {
    chat.loadSessions()
  }, [])

  const activeSession = chat.sessions.find((s) => s.id === chat.activeSessionId)

  return (
    <div
      style={{
        display: 'flex',
        height: '100vh',
        overflow: 'hidden',
        fontFamily,
        background: '#f0efee',
        position: 'relative',
      }}
    >
      <Sidebar
        collapsed={!sidebarOpen}
        onToggle={() => setSidebarOpen((v) => !v)}
        sessions={chat.sessions}
        activeSessionId={chat.activeSessionId}
        onSelectSession={chat.selectSession}
        onNewSession={() => chat.createSession()}
        onRenameSession={chat.renameSession}
        onDeleteSession={chat.deleteSession}
        onBatchDeleteSessions={chat.deleteSessions}
        user={user}
        onLogout={logout}
        onOpenSettings={() => setSettingsOpen(true)}
        isTemporarySession={chat.isTemporarySession}
      />

      <ChatArea
        title={activeSession?.title || '新对话'}
        messages={chat.messages}
        isStreaming={chat.isStreaming}
        onSend={chat.sendMessage}
        onStop={chat.stopStreaming}
        sidebarCollapsed={!sidebarOpen}
        onToggleSidebar={() => setSidebarOpen(true)}
        tableGroups={chat.tableGroups}
        selectedGroupId={chat.selectedGroupId}
        onSelectGroup={chat.selectGroup}
        tableGroupsLoading={chat.tableGroupsLoading}
        quickQuestions={chat.quickQuestions}
        inputValue={chat.inputValue}
        onInputChange={chat.setInputValue}
        onApplyQuickQuestion={chat.applyQuickQuestion}
        onCreateQuickQuestion={chat.createQuickQuestion}
      />

      <SettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        tableGroups={chat.tableGroups}
        quickQuestions={chat.quickQuestions}
        quickQuestionsLoading={chat.quickQuestionsLoading}
        onCreateQuickQuestion={chat.createQuickQuestion}
        onUpdateQuickQuestion={chat.updateQuickQuestion}
        onDeleteQuickQuestion={chat.deleteQuickQuestion}
        onReorderQuickQuestions={chat.reorderQuickQuestions}
      />
    </div>
  )
}
