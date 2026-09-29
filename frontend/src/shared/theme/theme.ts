import { createTheme, type Theme } from '@mui/material/styles';
import type { PaletteMode } from '@mui/material';

export function createAppTheme(mode: PaletteMode): Theme {
  const isDark = mode === 'dark';

  return createTheme({
    palette: {
      mode,
      primary: { main: isDark ? '#00bcd4' : '#0097a7' },
      secondary: { main: isDark ? '#ff4081' : '#d81b60' },
      error: { main: '#f44336' },
      warning: { main: isDark ? '#ff9800' : '#ed6c02' },
      success: { main: isDark ? '#4caf50' : '#2e7d32' },
      background: isDark
        ? { default: '#121212', paper: '#1e1e1e' }
        : { default: '#f4f6f8', paper: '#ffffff' },
      divider: isDark ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.12)',
    },
    typography: {
      fontFamily: '"Roboto Mono", "Roboto", monospace',
    },
    components: {
      MuiButton: {
        defaultProps: { size: 'small' },
      },
      MuiTextField: {
        defaultProps: { size: 'small', variant: 'outlined' },
      },
      MuiTable: {
        defaultProps: { size: 'small' },
      },
      MuiAppBar: {
        styleOverrides: {
          colorPrimary: ({ theme }) => ({
            ...(theme.palette.mode === 'light' && {
              backgroundColor: theme.palette.background.paper,
              color: theme.palette.text.primary,
              borderBottom: `1px solid ${theme.palette.divider}`,
            }),
          }),
        },
      },
    },
  });
}

const theme = createAppTheme('dark');

export default theme;
