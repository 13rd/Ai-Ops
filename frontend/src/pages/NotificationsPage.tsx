import { Error as ErrorIcon, Info as InfoIcon, Warning as WarningIcon } from '@mui/icons-material';
import {
  Box,
  Chip,
  Divider,
  FormControl,
  InputLabel,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Pagination,
  Select,
  Stack,
  Typography,
} from '@mui/material';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { NotificationSeverity } from '@/entities/Notification';
import { useMarkAsRead, useNotifications } from '@/features/notifications/hooks';
import { formatDate, fromNow } from '@/shared/utils/formatters';

const SEVERITY_ICON: Record<NotificationSeverity, React.ReactElement> = {
  low: <InfoIcon fontSize="small" color="info" />,
  medium: <WarningIcon fontSize="small" color="warning" />,
  high: <ErrorIcon fontSize="small" color="error" />,
  critical: <ErrorIcon fontSize="small" sx={{ color: 'error.dark' }} />,
};

const PAGE_SIZE = 20;

export default function NotificationsPage() {
  const navigate = useNavigate();
  const [readFilter, setReadFilter] = useState<string>('');
  const [page, setPage] = useState(1);

  const filters = {
    ...(readFilter === 'unread' ? { is_read: false } : readFilter === 'read' ? { is_read: true } : {}),
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  };

  const { data, isLoading } = useNotifications(filters);
  const markRead = useMarkAsRead();

  const notifications = data?.items ?? [];
  const total = data?.pagination?.total ?? 0;
  const pageCount = Math.ceil(total / PAGE_SIZE);

  async function handleClick(id: number, isRead: boolean, anomalyId: number | null) {
    if (!isRead) await markRead.mutateAsync(id);
    if (anomalyId) navigate(`/anomalies/${anomalyId}`);
  }

  return (
    <Box>
      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5">Уведомления</Typography>
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Фильтр</InputLabel>
          <Select value={readFilter} label="Фильтр" onChange={(e) => { setReadFilter(e.target.value); setPage(1); }}>
            <MenuItem value="">Все</MenuItem>
            <MenuItem value="unread">Непрочитанные</MenuItem>
            <MenuItem value="read">Прочитанные</MenuItem>
          </Select>
        </FormControl>
      </Stack>

      {isLoading ? (
        <Typography color="text.secondary">Загрузка…</Typography>
      ) : notifications.length === 0 ? (
        <Box sx={{ py: 8, textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">Уведомлений нет</Typography>
        </Box>
      ) : (
        <>
          <List disablePadding>
            {notifications.map((n, idx) => (
              <Box key={n.id}>
                <ListItem
                  alignItems="flex-start"
                  sx={{
                    cursor: n.anomaly_id ? 'pointer' : 'default',
                    bgcolor: n.is_read ? 'transparent' : 'action.hover',
                    borderRadius: 1,
                    '&:hover': { bgcolor: 'action.selected' },
                  }}
                  onClick={() => handleClick(n.id, n.is_read, n.anomaly_id)}
                >
                  <Box sx={{ mr: 1.5, mt: 0.5, flexShrink: 0 }}>
                    {SEVERITY_ICON[n.severity] ?? <InfoIcon fontSize="small" />}
                  </Box>
                  <ListItemText
                    primary={
                      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <Typography variant="body2" sx={{ fontWeight: n.is_read ? 400 : 600 }}>
                          {n.title}
                        </Typography>
                        <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexShrink: 0, ml: 1 }}>
                          {!n.is_read && <Chip label="новое" size="small" color="primary" />}
                          <Typography variant="caption" color="text.disabled" sx={{ whiteSpace: 'nowrap' }}>
                            {fromNow(n.sent_at)}
                          </Typography>
                        </Stack>
                      </Stack>
                    }
                    secondary={
                      <Stack spacing={0.5} sx={{ mt: 0.25 }}>
                        <Typography variant="body2" color="text.secondary">{n.body}</Typography>
                        <Typography variant="caption" color="text.disabled">{formatDate(n.sent_at)}</Typography>
                      </Stack>
                    }
                  />
                </ListItem>
                {idx < notifications.length - 1 && <Divider component="li" />}
              </Box>
            ))}
          </List>

          {pageCount > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
              <Pagination count={pageCount} page={page} onChange={(_, p) => setPage(p)} color="primary" size="small" />
            </Box>
          )}
        </>
      )}
    </Box>
  );
}
