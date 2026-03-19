/**
 * Nobi Design System — Dark theme with purple accents.
 * Matches projectnobi.ai branding.
 */

export const theme = {
  colors: {
    background: '#0a0a0f',
    surface: '#12121a',
    card: 'rgba(255,255,255,0.03)',
    primary: '#6C5CE7',
    primaryLight: '#A29BFE',
    secondary: '#FFA502',
    text: '#FFFFFF',
    textSecondary: '#A0A0B0',
    textMuted: '#666680',
    success: '#00D2D3',
    error: '#FF6B6B',
    border: 'rgba(255,255,255,0.06)',
    userBubble: '#6C5CE7',
    noriBubble: '#1a1a2e',
    overlay: 'rgba(0,0,0,0.6)',
  },
  spacing: {
    xs: 4,
    sm: 8,
    md: 16,
    lg: 24,
    xl: 32,
  },
  borderRadius: {
    sm: 8,
    md: 12,
    lg: 16,
    xl: 24,
    pill: 999,
  },
  fontSize: {
    xs: 12,
    sm: 14,
    md: 16,
    lg: 20,
    xl: 28,
    xxl: 36,
  },
  shadow: {
    sm: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.25,
      shadowRadius: 3.84,
      elevation: 2,
    },
    md: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.3,
      shadowRadius: 4.65,
      elevation: 6,
    },
  },
} as const;

export type Theme = typeof theme;
export type ThemeColors = keyof typeof theme.colors;
