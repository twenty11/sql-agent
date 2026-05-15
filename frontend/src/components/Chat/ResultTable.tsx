import { useState } from 'react'
import type { QueryResult } from '../../types/chat'
import { colors, radii, fontFamily } from '../../styles/tokens'
import { ExportIcon } from '../Icons'
import { Tooltip } from '../ui/Tooltip'
import { chatService } from '../../services/chat'

interface ResultTableProps {
  result: QueryResult
  queryResultId?: string
}

export function ResultTable({ result, queryResultId }: ResultTableProps) {
  const { columns, rows, row_count } = result
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const canExport = !!queryResultId && !exporting
  const truncated = !!result.truncated
  const previewCount = result.preview_row_count ?? row_count
  const headerHeight = 36
  const headerTrackBackground =
    `linear-gradient(to bottom, ` +
    `${colors.tableHeadBg} 0, ` +
    `${colors.tableHeadBg} ${headerHeight}px, ` +
    `${colors.border} ${headerHeight}px, ` +
    `${colors.border} ${headerHeight + 1}px, ` +
    `#ffffff ${headerHeight + 1}px, ` +
    `#ffffff 100%)`

  const exportXLSX = async () => {
    if (!queryResultId || exporting) return
    setExporting(true)
    setExportError(null)
    try {
      const { blob, filename } = await chatService.exportQueryResult(queryResultId)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch {
      setExportError('导出失败，请稍后重试')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div
      style={{
        border: `1px solid ${colors.border}`,
        borderRadius: radii.xxl,
        overflow: 'hidden',
      }}
    >
      {/* 标题行 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 14px',
          borderBottom: `1px solid ${colors.border}`,
          background: 'rgba(0,0,0,0.05)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'rgba(0,0,0,0.85)', fontFamily }}>
            查询结果
          </span>
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            padding: '2px 10px',
            background: colors.pillBg,
            color: colors.pillText,
            borderRadius: radii.pill,
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: '0.125px',
          }}>
            {truncated ? `仅展示前 ${previewCount} 行` : `${row_count} 行`}
          </span>
        </div>
        <Tooltip content={queryResultId ? '导出完整 Excel' : '查询完成后可导出完整结果'}>
          <button
            onClick={exportXLSX}
            disabled={!canExport}
            style={{
              border: 'none',
              background: 'transparent',
              cursor: canExport ? 'pointer' : 'not-allowed',
              display: 'flex',
              alignItems: 'center',
              padding: '4px',
              borderRadius: radii.sm,
              color: canExport ? colors.textSecondary : colors.textMuted,
              opacity: canExport ? 1 : 0.55,
              transition: 'background 0.15s ease',
            }}
            onMouseEnter={(e) => {
              if (canExport) e.currentTarget.style.background = colors.hoverBg
            }}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <ExportIcon width={14} height={14} color="currentColor" />
          </button>
        </Tooltip>
      </div>

      {/* 表格内容 */}
      <div style={{ overflow: 'auto', maxHeight: 320, background: headerTrackBackground }}>
        <table style={{ width: '100%', minWidth: '100%', borderCollapse: 'collapse', fontSize: 13, fontFamily }}>
          <thead style={{ position: 'sticky', top: 0, zIndex: 1 }}>
            <tr>
              {columns.map((col) => (
                <th
                  key={col}
                  style={{
                    padding: '10px 14px',
                    textAlign: 'left',
                    fontSize: 12,
                    fontWeight: 600,
                    color: colors.textSecondary,
                    background: colors.tableHeadBg,
                    borderBottom: `1px solid ${colors.border}`,
                    whiteSpace: 'nowrap',
                  }}
                >
                  {col}
                </th>
              ))}
              {/* 填充列：撑满行尾剩余宽度，保证背景和下框线延伸到右边缘 */}
              <th
                aria-hidden="true"
                style={{
                  width: '100%',
                  minWidth: 24,
                  background: colors.tableHeadBg,
                  borderBottom: `1px solid ${colors.border}`,
                  padding: 0,
                }}
              />
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length + 1}
                  style={{
                    padding: '14px',
                    color: colors.textMuted,
                    textAlign: 'center',
                  }}
                >
                  查询成功，返回 0 行
                </td>
              </tr>
            ) : rows.slice(0, 100).map((row, i) => (
              <tr
                key={i}
                style={{ borderBottom: `1px solid rgba(0,0,0,0.05)` }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(0,0,0,0.03)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                {row.map((cell, j) => (
                  <td
                    key={j}
                    style={{
                      padding: '10px 14px',
                      color: colors.textPrimary,
                      maxWidth: 200,
                    }}
                  >
                    <Tooltip content={cell === null ? 'null' : String(cell)}>
                      <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {cell === null ? (
                          <span style={{ color: colors.textMuted, fontStyle: 'italic' }}>null</span>
                        ) : (
                          String(cell)
                        )}
                      </div>
                    </Tooltip>
                  </td>
                ))}
                <td />
              </tr>
            ))}
          </tbody>
        </table>
        {(row_count > 100 || truncated || exportError) && (
          <div
            style={{
              padding: '8px 12px',
              fontSize: 12,
              color: exportError ? colors.errorColor : colors.textMuted,
              fontFamily,
              borderTop: `1px solid ${colors.border}`,
              background: colors.tableHeadBg,
            }}
          >
            {exportError || (
              truncated
                ? `结果较多，当前仅展示前 ${previewCount} 行，可导出 Excel 查看完整数据`
                : `仅显示前 100 行，共 ${row_count} 行`
            )}
          </div>
        )}
      </div>
    </div>
  )
}
