import React from 'react'
import { colors, radii, shadows, fontFamily } from '../../styles/tokens'

interface ConfirmDialogProps {
  open: boolean
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmText = '确认',
  cancelText = '取消',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!open) return null

  return (
    <>
      {/* 遮罩层 */}
      <div
        onClick={onCancel}
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.4)',
          zIndex: 1000,
        }}
      />

      {/* 卡片对话框 */}
      <div
        style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          zIndex: 1001,
          background: colors.pageBg,
          borderRadius: radii.xl,
          boxShadow: shadows.card,
          padding: '24px',
          width: 320,
          animation: 'fadeIn 0.12s ease',
        }}
      >
        {/* 标题 */}
        <div
          style={{
            fontSize: 16,
            fontWeight: 600,
            color: colors.textPrimary,
            marginBottom: 12,
            fontFamily,
          }}
        >
          {title}
        </div>

        {/* 消息内容 */}
        <div
          style={{
            fontSize: 14,
            color: colors.textSecondary,
            lineHeight: 1.5,
            marginBottom: 24,
            fontFamily,
          }}
        >
          {message}
        </div>

        {/* 按钮区域 */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: 12,
          }}
        >
          <button
            onClick={onCancel}
            style={{
              padding: '8px 16px',
              border: `1px solid ${colors.borderInput}`,
              borderRadius: radii.md,
              background: colors.pageBg,
              color: colors.textPrimary,
              fontSize: 14,
              fontFamily,
              cursor: 'pointer',
              transition: 'background 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = colors.hoverBg)}
            onMouseLeave={(e) => (e.currentTarget.style.background = colors.pageBg)}
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            style={{
              padding: '8px 16px',
              border: 'none',
              borderRadius: radii.md,
              background: colors.errorColor,
              color: colors.textWhite,
              fontSize: 14,
              fontFamily,
              cursor: 'pointer',
              transition: 'background 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = '#c44d00')}
            onMouseLeave={(e) => (e.currentTarget.style.background = colors.errorColor)}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </>
  )
}
