/** Notion Design System 颜色/字体/阴影令牌 */

export const colors = {
  pageBg: '#ffffff',
  inputBg: '#f4f4f4',
  sidebarBg: '#f6f5f4',
  rightPanelBg: '#ffffff',
  textPrimary: 'rgba(0,0,0,0.95)',
  textSecondary: '#615d59',
  textMuted: '#a39e98',
  border: 'rgba(0,0,0,0.1)',
  borderLight: 'rgba(0,0,0,0.08)',
  borderStrong: 'rgba(0,0,0,0.12)',
  borderInput: 'rgba(0,0,0,0.12)',
  accent: '#0075de',
  accentHover: '#005bab',
  accentActive: '#004a94',
  pillBg: '#f2f9ff',
  pillText: '#097fe8',
  codeBg: '#1c1c1e',
  codeText: '#e0ddd8',
  hoverBg: 'rgba(0,0,0,0.05)',
  activeBg: 'rgba(0,0,0,0.07)',
  userMsgBg: '#e8e6e3',
  errorColor: '#d95454',
  successColor: '#0f7b6c',
  textWhite: '#ffffff',
  accentFocus: '#097fe8',
  bgSqlCollapsed: '#f6f5f4',
  tableHeadBg: '#faf9f8',
  adminBadgeBg: '#fef3e2',
  adminBadgeText: '#b45309',
  analystBadgeBg: '#f2f9ff',
  analystBadgeText: '#097fe8',
  viewerBadgeBg: '#f0f0ef',
  viewerBadgeText: '#615d59',
} as const

export const shadows = {
  card: `rgba(0,0,0,0.04) 0px 4px 18px,
         rgba(0,0,0,0.027) 0px 2.025px 7.84688px,
         rgba(0,0,0,0.02) 0px 0.8px 2.925px,
         rgba(0,0,0,0.01) 0px 0.175px 1.04062px`,
  input: `rgba(0,0,0,0.04) 0px 4px 18px,
          rgba(0,0,0,0.027) 0px 2.025px 7.84688px,
          rgba(0,0,0,0.02) 0px 0.8px 2.925px,
          rgba(0,0,0,0.01) 0px 0.175px 1.04062px`,
} as const

export const radii = {
  sm: '6px',
  md: '8px',
  btn: '6px',
  listItem: '8px',
  avatar: '10px',
  code: '12px',
  table: '12px',
  card: '16px',
  pill: '9999px',
  lg: '10px',
  xl: '12px',
  xxl: '16px',
  input: '28px',
} as const

export const fontFamily =
  "Inter, -apple-system, system-ui, 'Segoe UI', Helvetica, Arial, sans-serif"

export const fontMono =
  "Menlo, Monaco, 'Courier New', monospace"

export const fontSizes = {
  xs: 12,
  sm: 13,
  base: 14,
  md: 15,
  lg: 16,
  xl: 18,
  xxl: 22,
} as const

// Google Material Design avatar color palette — muted, varied, easy on the eyes
const AVATAR_COLORS = [
  '#5C6BC0', // indigo
  '#42A5F5', // light blue (softer than accent)
  '#26A69A', // teal
  '#66BB6A', // green
  '#D4E157', // lime — skip, too light; kept for index parity
  '#FFA726', // orange
  '#EF5350', // red
  '#EC407A', // pink
  '#AB47BC', // purple
  '#7E57C2', // deep purple
  '#29B6F6', // cyan
  '#26C6DA', // teal-ish
  '#8D6E63', // brown
  '#78909C', // blue-grey
] as const

/** Returns a deterministic avatar background color based on the identifier string. */
export function getAvatarColor(identifier: string): string {
  let hash = 0
  for (let i = 0; i < identifier.length; i++) {
    hash = identifier.charCodeAt(i) + ((hash << 5) - hash)
  }
  const index = Math.abs(hash) % AVATAR_COLORS.length
  return AVATAR_COLORS[index]
}
