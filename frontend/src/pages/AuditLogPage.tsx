import {
  Download as DownloadIcon,
  Security as SecurityIcon,
  Visibility as ViewIcon,
} from '@mui/icons-material';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  Drawer,
  FormControl,
  Grid,
  IconButton,
  InputLabel,
  MenuItem,
  Pagination,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { useState } from 'react';
import type { AuditLogEntry, AuditLogFilters } from '@/entities/AuditLog';
import { AUDIT_ACTIONS, AUDIT_RESOURCE_TYPES } from '@/entities/AuditLog';
import { useAuditLog } from '@/features/audit/hooks';
import { useUsers } from '@/features/users/hooks';
import { formatDate } from '@/shared/utils/formatters';

const PAGE_SIZE = 50;

const ACTION_COLOR: Record<string, 'error' | 'warning' | 'success' | 'info' | 'default'> = {
  login: 'success',
  login_failed: 'error',
  logout: 'default',
  user_deactivated: 'warning',
  server_deleted: 'error',
  recommendation_approved: 'success',
  recommendation_rejected: 'error',
  anomaly_status_changed: 'info',
};

const ACTION_LABEL: Record<string, string> = {
  login: 'Вход',
  login_failed: 'Неудачный вход',
  logout: 'Выход',
  user_deactivated: 'Деактивация пользователя',
  server_deleted: 'Удаление сервера',
  recommendation_approved: 'Рекомендация одобрена',
  recommendation_rejected: 'Рекомендация отклонена',
  anomaly_status_changed: 'Статус аномалии изменён',
};

function actionColor(action: string): 'error' | 'warning' | 'success' | 'info' | 'default' {
  return ACTION_COLOR[action] ?? 'default';
}

function labelAction(action: string): string {
  return ACTION_LABEL[action] ?? action.replace(/_/g, ' ');
}

function exportCsv(entries: AuditLogEntry[], usernameMap: Map<number, string>) {
  const header = ['ID', 'Время', 'Пользователь', 'Действие', 'Тип ресурса', 'ID ресурса', 'IP', 'Детали'];
  const rows = entries.map((e) => [
    e.id,
    formatDate(e.created_at),
    e.user_id ? (usernameMap.get(e.user_id) ?? String(e.user_id)) : '',
    e.action,
    e.resource_type ?? '',
    e.resource_id ?? '',
    e.ip_address ?? '',
    JSON.stringify(e.details),
  ]);
  const csvContent = [header, ...rows]
    .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    .join('\n');
  const blob = new Blob(['﻿' + csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `audit-log-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function AuditLogPage() {
  const [page, setPage] = useState(1);
  const [userId, setUserId] = useState<string>('');
  const [action, setAction] = useState('');
  const [resourceType, setResourceType] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [detailsEntry, setDetailsEntry] = useState<AuditLogEntry | null>(null);

  const { data: usersData } = useUsers(200, 0);
  const users = usersData?.items ?? [];
  const usernameMap = new Map(users.map((u) => [u.id, u.username]));

  const filters: AuditLogFilters = {
    ...(userId ? { user_id: parseInt(userId, 10) } : {}),
    ...(action ? { action } : {}),
    ...(resourceType ? { resource_type: resourceType } : {}),
    ...(dateFrom ? { from: new Date(dateFrom).toISOString() } : {}),
    ...(dateTo ? { to: new Date(dateTo).toISOString() } : {}),
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  };

  const { data, isLoading, isError } = useAuditLog(filters);
  const entries = data?.items ?? [];
  const total = data?.pagination?.total ?? 0;
  const pageCount = Math.ceil(total / PAGE_SIZE);

  function resetFilters() { setUserId(''); setAction(''); setResourceType(''); setDateFrom(''); setDateTo(''); setPage(1); }

  return (
    <Box>
      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
          <SecurityIcon />
          <Typography variant="h5">Журнал аудита</Typography>
          {total > 0 && <Chip label={total} size="small" />}
        </Stack>
        <Button startIcon={<DownloadIcon />} variant="outlined" size="small" disabled={entries.length === 0} onClick={() => exportCsv(entries, usernameMap)}>
          Экспорт CSV
        </Button>
      </Stack>

      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Grid container spacing={2} sx={{ alignItems: 'flex-end' }}>
          <Grid size={{ xs: 12, sm: 6, md: 3, lg: 2 }}>
            <FormControl fullWidth size="small">
              <InputLabel>Пользователь</InputLabel>
              <Select value={userId} label="Пользователь" onChange={(e) => { setUserId(e.target.value); setPage(1); }}>
                <MenuItem value="">Все</MenuItem>
                {users.map((u) => <MenuItem key={u.id} value={String(u.id)}>{u.username}</MenuItem>)}
              </Select>
            </FormControl>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3, lg: 3 }}>
            <FormControl fullWidth size="small">
              <InputLabel>Действие</InputLabel>
              <Select value={action} label="Действие" onChange={(e) => { setAction(e.target.value); setPage(1); }}>
                <MenuItem value="">Все</MenuItem>
                {AUDIT_ACTIONS.map((a) => <MenuItem key={a} value={a}>{labelAction(a)}</MenuItem>)}
              </Select>
            </FormControl>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 2, lg: 2 }}>
            <FormControl fullWidth size="small">
              <InputLabel>Тип ресурса</InputLabel>
              <Select value={resourceType} label="Тип ресурса" onChange={(e) => { setResourceType(e.target.value); setPage(1); }}>
                <MenuItem value="">Все</MenuItem>
                {AUDIT_RESOURCE_TYPES.map((r) => <MenuItem key={r} value={r}>{r}</MenuItem>)}
              </Select>
            </FormControl>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 2, lg: 2 }}>
            <TextField label="С" type="date" size="small" fullWidth value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(1); }} slotProps={{ inputLabel: { shrink: true } }} />
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 2, lg: 2 }}>
            <TextField label="По" type="date" size="small" fullWidth value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(1); }} slotProps={{ inputLabel: { shrink: true } }} />
          </Grid>

          <Grid size={{ xs: 12, sm: 'auto' }}>
            <Button size="small" onClick={resetFilters}>Сбросить</Button>
          </Grid>
        </Grid>
      </Paper>

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}><CircularProgress /></Box>
      ) : isError ? (
        <Alert severity="error">Не удалось загрузить журнал аудита.</Alert>
      ) : entries.length === 0 ? (
        <Box sx={{ py: 8, textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">Записей не найдено</Typography>
        </Box>
      ) : (
        <>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Время</TableCell>
                  <TableCell>Пользователь</TableCell>
                  <TableCell>Действие</TableCell>
                  <TableCell>Ресурс</TableCell>
                  <TableCell>IP</TableCell>
                  <TableCell align="right">Детали</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {entries.map((e) => (
                  <TableRow key={e.id} hover>
                    <TableCell>
                      <Typography variant="caption" sx={{ fontFamily: 'monospace', whiteSpace: 'nowrap' }}>{formatDate(e.created_at)}</Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">{e.user_id ? (usernameMap.get(e.user_id) ?? `#${e.user_id}`) : '—'}</Typography>
                    </TableCell>
                    <TableCell>
                      <Chip label={labelAction(e.action)} size="small" color={actionColor(e.action)} sx={{ fontSize: '0.7rem' }} />
                    </TableCell>
                    <TableCell>
                      {e.resource_type ? (
                        <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center' }}>
                          <Typography variant="body2">{e.resource_type}</Typography>
                          {e.resource_id && <Typography variant="caption" color="text.secondary">#{e.resource_id}</Typography>}
                        </Stack>
                      ) : <Typography variant="body2" color="text.disabled">—</Typography>}
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace' }}>{e.ip_address ?? '—'}</Typography>
                    </TableCell>
                    <TableCell align="right">
                      {Object.keys(e.details).length > 0 && (
                        <Tooltip title="Просмотреть детали">
                          <IconButton size="small" onClick={() => setDetailsEntry(e)}><ViewIcon fontSize="small" /></IconButton>
                        </Tooltip>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {pageCount > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
              <Pagination count={pageCount} page={page} onChange={(_, p) => setPage(p)} color="primary" size="small" />
            </Box>
          )}
        </>
      )}

      <Drawer anchor="right" open={Boolean(detailsEntry)} onClose={() => setDetailsEntry(null)} slotProps={{ paper: { sx: { width: { xs: '100%', sm: 480 }, p: 3 } } }}>
        {detailsEntry && (
          <Box>
            <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">Запись #{detailsEntry.id}</Typography>
              <Button size="small" onClick={() => setDetailsEntry(null)}>Закрыть</Button>
            </Stack>

            <Divider sx={{ mb: 2 }} />

            <Stack spacing={1.5} sx={{ mb: 2 }}>
              <Stack direction="row" spacing={2}>
                <Typography variant="caption" color="text.secondary" sx={{ minWidth: 100 }}>Время</Typography>
                <Typography variant="body2">{formatDate(detailsEntry.created_at)}</Typography>
              </Stack>
              <Stack direction="row" spacing={2}>
                <Typography variant="caption" color="text.secondary" sx={{ minWidth: 100 }}>Пользователь</Typography>
                <Typography variant="body2">{detailsEntry.user_id ? (usernameMap.get(detailsEntry.user_id) ?? `#${detailsEntry.user_id}`) : '—'}</Typography>
              </Stack>
              <Stack direction="row" spacing={2} sx={{ alignItems: 'center' }}>
                <Typography variant="caption" color="text.secondary" sx={{ minWidth: 100 }}>Действие</Typography>
                <Chip label={labelAction(detailsEntry.action)} size="small" color={actionColor(detailsEntry.action)} />
              </Stack>
              {detailsEntry.resource_type && (
                <Stack direction="row" spacing={2}>
                  <Typography variant="caption" color="text.secondary" sx={{ minWidth: 100 }}>Ресурс</Typography>
                  <Typography variant="body2">{detailsEntry.resource_type}{detailsEntry.resource_id && ` #${detailsEntry.resource_id}`}</Typography>
                </Stack>
              )}
              {detailsEntry.ip_address && (
                <Stack direction="row" spacing={2}>
                  <Typography variant="caption" color="text.secondary" sx={{ minWidth: 100 }}>IP</Typography>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{detailsEntry.ip_address}</Typography>
                </Stack>
              )}
              {detailsEntry.user_agent && (
                <Stack direction="row" spacing={2}>
                  <Typography variant="caption" color="text.secondary" sx={{ minWidth: 100 }}>User Agent</Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ wordBreak: 'break-all' }}>{detailsEntry.user_agent}</Typography>
                </Stack>
              )}
            </Stack>

            <Divider sx={{ mb: 2 }} />

            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>Детали</Typography>
            <Box component="pre" sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 1, fontFamily: 'monospace', fontSize: '0.8rem', overflowX: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word', m: 0 }}>
              {JSON.stringify(detailsEntry.details, null, 2)}
            </Box>
          </Box>
        )}
      </Drawer>
    </Box>
  );
}
