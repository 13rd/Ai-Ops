import {
  AccountCircle as AccountCircleIcon,
  Assessment as AssessmentIcon,
  BugReport as BugReportIcon,
  Dashboard as DashboardIcon,
  DarkMode as DarkModeIcon,
  LightMode as LightModeIcon,
  Notifications as NotificationsIcon,
  People as PeopleIcon,
  Security as SecurityIcon,
  SmartToy as SmartToyIcon,
  Storage as StorageIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import {
  AppBar,
  Avatar,
  Box,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Toolbar,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import { useState } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '@/features/auth/AuthContext';
import { useColorMode } from '@/shared/theme/ColorModeProvider';
import { NotificationBell } from '@/widgets/NotificationBell';

const DRAWER_WIDTH = 220;

interface NavItem {
  label: string;
  icon: React.ReactElement;
  path: string;
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Дашборд', icon: <DashboardIcon />, path: '/' },
  { label: 'Серверы', icon: <StorageIcon />, path: '/servers' },
  { label: 'Аномалии', icon: <WarningIcon />, path: '/anomalies' },
  { label: 'Уведомления', icon: <NotificationsIcon />, path: '/notifications' },
  { label: 'Пользователи', icon: <PeopleIcon />, path: '/users', adminOnly: true },
  { label: 'Журнал аудита', icon: <SecurityIcon />, path: '/audit-log', adminOnly: true },
  { label: 'Настройки LLM', icon: <SmartToyIcon />, path: '/llm-settings', adminOnly: true },
  { label: 'Отчёты', icon: <AssessmentIcon />, path: '/reports' },
  ...(import.meta.env.VITE_DEMO_MODE === 'true'
    ? [{ label: 'Demo Panel', icon: <BugReportIcon />, path: '/demo' }]
    : []),
];

export function AppShell() {
  const { user, isAdmin, logout } = useAuth();
  const { mode, toggleColorMode } = useColorMode();
  const navigate = useNavigate();
  const theme = useTheme();
  const isMd = useMediaQuery(theme.breakpoints.up('md'));
  const [mobileOpen, setMobileOpen] = useState(false);
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  const visibleItems = NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin);

  const drawerContent = (
    <Box>
      <Toolbar>
        <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }} noWrap>
          Server Monitor
        </Typography>
      </Toolbar>
      <Divider />
      <List dense>
        {visibleItems.map((item) => (
          <ListItemButton
            key={item.path}
            onClick={() => {
              navigate(item.path);
              setMobileOpen(false);
            }}
          >
            <ListItemIcon sx={{ minWidth: 36 }}>{item.icon}</ListItemIcon>
            <ListItemText primary={item.label} />
          </ListItemButton>
        ))}
      </List>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', width: '100%', minHeight: '100vh' }}>
      {}
      <AppBar position="fixed" sx={{ zIndex: (t) => t.zIndex.drawer + 1 }} elevation={0}>
        <Toolbar variant="dense">
          {!isMd && (
            <IconButton edge="start" onClick={() => setMobileOpen((v) => !v)} sx={{ mr: 1 }}>
              <DashboardIcon />
            </IconButton>
          )}
          <Typography variant="h6" noWrap sx={{ flexGrow: 1, fontWeight: 700 }}>
            Server Monitor
          </Typography>

          <Tooltip title={mode === 'dark' ? 'Светлая тема' : 'Тёмная тема'}>
            <IconButton onClick={toggleColorMode} sx={{ mr: 0.5 }}>
              {mode === 'dark' ? <LightModeIcon /> : <DarkModeIcon />}
            </IconButton>
          </Tooltip>

          <NotificationBell />

          <Tooltip title={user?.username ?? ''}>
            <IconButton onClick={(e) => setAnchorEl(e.currentTarget)}>
              <Avatar sx={{ width: 28, height: 28, bgcolor: 'primary.main', fontSize: 13 }}>
                {user?.username?.[0]?.toUpperCase() ?? <AccountCircleIcon fontSize="small" />}
              </Avatar>
            </IconButton>
          </Tooltip>
          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={() => setAnchorEl(null)}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            transformOrigin={{ vertical: 'top', horizontal: 'right' }}
          >
            <MenuItem onClick={() => { setAnchorEl(null); navigate('/profile'); }}>
              Профиль
            </MenuItem>
            <Divider />
            <MenuItem onClick={async () => { setAnchorEl(null); await logout(); navigate('/login'); }}>
              Выйти
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>

      {}
      <Box component="nav" sx={{ width: { md: DRAWER_WIDTH }, flexShrink: 0 }}>
        {}
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: 'block', md: 'none' },
            '& .MuiDrawer-paper': { width: DRAWER_WIDTH, boxSizing: 'border-box' },
          }}
        >
          {drawerContent}
        </Drawer>
        {}
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', md: 'block' },
            '& .MuiDrawer-paper': {
              width: DRAWER_WIDTH,
              boxSizing: 'border-box',
              borderRight: '1px solid',
              borderColor: 'divider',
            },
          }}
          open
        >
          {drawerContent}
        </Drawer>
      </Box>

      {}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: { xs: 2, md: 3 },
          mt: '48px',
          minWidth: 0,
          minHeight: 'calc(100vh - 48px)',
          overflow: 'auto',
        }}
      >
        <Outlet />
      </Box>
    </Box>
  );
}
