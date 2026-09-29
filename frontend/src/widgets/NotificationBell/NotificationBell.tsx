import {
  NotificationsNone as BellIcon,
  Circle as DotIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import {
  Badge,
  Box,
  Button,
  Divider,
  IconButton,
  List,
  ListItem,
  ListItemText,
  Popover,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import { useSnackbar } from 'notistack';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { AppNotification, NotificationSeverity } from '@/entities/Notification';
import { useMarkAsRead, useUnreadNotifications } from '@/features/notifications/hooks';
import { fromNow } from '@/shared/utils/formatters';

const SEVERITY_ICON: Record<NotificationSeverity, React.ReactElement> = {
  low: <InfoIcon fontSize="small" color="info" />,
  medium: <WarningIcon fontSize="small" color="warning" />,
  high: <ErrorIcon fontSize="small" color="error" />,
  critical: <ErrorIcon fontSize="small" sx={{ color: 'error.dark' }} />,
};

export function NotificationBell() {
  const navigate = useNavigate();
  const { enqueueSnackbar } = useSnackbar();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);

  const { data } = useUnreadNotifications();
  const notifications: AppNotification[] = data?.items ?? [];
  const unreadCount = data?.pagination?.total ?? 0;
  const markRead = useMarkAsRead();

  const seenIds = useRef<Set<number>>(new Set());
  const isFirstLoad = useRef(true);

  useEffect(() => {
    if (!data) return;
    if (isFirstLoad.current) {
      data.items.forEach((n) => seenIds.current.add(n.id));
      isFirstLoad.current = false;
      return;
    }
    for (const n of data.items) {
      if (!seenIds.current.has(n.id) && ['medium', 'high', 'critical'].includes(n.severity)) {
        enqueueSnackbar(n.title, {
          variant: n.severity === 'low' ? 'info' : n.severity === 'medium' ? 'warning' : 'error',
          autoHideDuration: 5000,
        });
      }
      seenIds.current.add(n.id);
    }
  }, [data, enqueueSnackbar]);

  async function handleMarkRead(n: AppNotification, e: React.MouseEvent) {
    e.stopPropagation();
    if (!n.is_read) await markRead.mutateAsync(n.id);
  }

  return (
    <>
      <Tooltip title="Уведомления">
        <IconButton onClick={(e) => setAnchor(e.currentTarget)}>
          <Badge badgeContent={unreadCount || undefined} color="error" max={99}>
            <BellIcon />
          </Badge>
        </IconButton>
      </Tooltip>

      <Popover
        open={Boolean(anchor)}
        anchorEl={anchor}
        onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        slotProps={{ paper: { sx: { width: 360, maxHeight: 480 } } }}
      >
        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', px: 2, py: 1 }}>
          <Typography variant="subtitle2">
            Уведомления
            {unreadCount > 0 && (
              <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                ({unreadCount} непрочитанных)
              </Typography>
            )}
          </Typography>
          <Button size="small" onClick={() => { setAnchor(null); navigate('/notifications'); }}>
            Все
          </Button>
        </Stack>

        <Divider />

        {notifications.length === 0 ? (
          <Box sx={{ py: 4, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">Непрочитанных уведомлений нет</Typography>
          </Box>
        ) : (
          <List dense disablePadding>
            {notifications.map((n, idx) => (
              <Box key={n.id}>
                <ListItem
                  alignItems="flex-start"
                  sx={{
                    cursor: 'pointer',
                    bgcolor: n.is_read ? 'transparent' : 'action.hover',
                    '&:hover': { bgcolor: 'action.selected' },
                    pr: 1,
                  }}
                  onClick={(e) => handleMarkRead(n, e)}
                  secondaryAction={!n.is_read ? <DotIcon sx={{ fontSize: 10, color: 'primary.main', mt: 1 }} /> : null}
                >
                  <Box sx={{ mr: 1, mt: 0.5, flexShrink: 0 }}>
                    {SEVERITY_ICON[n.severity] ?? <InfoIcon fontSize="small" />}
                  </Box>
                  <ListItemText
                    primary={
                      <Typography variant="body2" sx={{ fontWeight: n.is_read ? 400 : 600 }}>
                        {n.title}
                      </Typography>
                    }
                    secondary={
                      <Stack spacing={0.25}>
                        <Typography variant="caption" color="text.secondary" noWrap>{n.body}</Typography>
                        <Typography variant="caption" color="text.disabled">{fromNow(n.sent_at)}</Typography>
                      </Stack>
                    }
                  />
                </ListItem>
                {idx < notifications.length - 1 && <Divider component="li" />}
              </Box>
            ))}
          </List>
        )}
      </Popover>
    </>
  );
}
