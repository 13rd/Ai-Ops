import { BugReport as BugIcon } from '@mui/icons-material';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  Grid,
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
  Typography,
} from '@mui/material';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { AnomalyFilters, AnomalySeverity, AnomalyStatus, AnomalyType } from '@/entities/Anomaly';
import { ANOMALY_SEVERITIES, ANOMALY_STATUSES, ANOMALY_TYPES } from '@/entities/Anomaly';
import { useAnomalies } from '@/features/anomalies/hooks';
import { useServers } from '@/features/servers/hooks';
import { formatDate } from '@/shared/utils/formatters';

const SEVERITY_COLOR: Record<AnomalySeverity, 'default' | 'info' | 'warning' | 'error'> = {
  low: 'info',
  medium: 'warning',
  high: 'error',
  critical: 'error',
};

const SEVERITY_LABEL: Record<AnomalySeverity, string> = {
  low: 'Низкая',
  medium: 'Средняя',
  high: 'Высокая',
  critical: 'Критическая',
};

const STATUS_COLOR: Record<AnomalyStatus, 'error' | 'warning' | 'success' | 'default'> = {
  open: 'error',
  investigating: 'warning',
  resolved: 'success',
};

const STATUS_LABEL: Record<AnomalyStatus, string> = {
  open: 'Открыта',
  investigating: 'Изучается',
  resolved: 'Решена',
};

const ANOMALY_TYPE_LABEL: Record<string, string> = {
  cpu_spike: 'Пик CPU',
  memory_leak: 'Утечка памяти',
  disk_pressure: 'Нагрузка диска',
  disk_fill: 'Заполнение диска',
  network_anomaly: 'Сетевая аномалия',
  network_storm: 'Сетевой шторм',
  container_crash: 'Сбой контейнера',
  service_down: 'Сервис недоступен',
};

function labelFor(type: AnomalyType): string {
  return ANOMALY_TYPE_LABEL[type] ?? type.replace(/_/g, ' ');
}

const PAGE_SIZE = 20;

export default function AnomaliesPage() {
  const navigate = useNavigate();
  const { data: serversData } = useServers({ limit: 1000 });

  const [serverId, setServerId] = useState<string>('');
  const [type, setType] = useState<string>('');
  const [severity, setSeverity] = useState<string>('');
  const [status, setStatus] = useState<string>('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(1);

  const filters: AnomalyFilters = {
    ...(serverId ? { server_id: parseInt(serverId, 10) } : {}),
    ...(type ? { type } : {}),
    ...(severity ? { severity } : {}),
    ...(status ? { status } : {}),
    ...(dateFrom ? { from: new Date(dateFrom).toISOString() } : {}),
    ...(dateTo ? { to: new Date(dateTo).toISOString() } : {}),
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  };

  const { data, isLoading, isError } = useAnomalies(filters);

  const servers = serversData?.items ?? [];
  const anomalies = data?.items ?? [];
  const total = data?.pagination?.total ?? 0;
  const pageCount = Math.ceil(total / PAGE_SIZE);

  function handleFilterChange() { setPage(1); }

  return (
    <Box>
      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
          <BugIcon color="warning" />
          <Typography variant="h5">Аномалии</Typography>
          {total > 0 && <Chip label={total} size="small" color="default" />}
        </Stack>
      </Stack>

      {}
      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Grid container spacing={2} sx={{ alignItems: 'flex-end' }}>
          <Grid size={{ xs: 12, sm: 6, md: 3, lg: 2 }}>
            <FormControl fullWidth size="small">
              <InputLabel>Сервер</InputLabel>
              <Select value={serverId} label="Сервер" onChange={(e) => { setServerId(e.target.value); handleFilterChange(); }}>
                <MenuItem value="">Все серверы</MenuItem>
                {servers.map((s) => <MenuItem key={s.id} value={String(s.id)}>{s.name}</MenuItem>)}
              </Select>
            </FormControl>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3, lg: 2 }}>
            <FormControl fullWidth size="small">
              <InputLabel>Тип</InputLabel>
              <Select value={type} label="Тип" onChange={(e) => { setType(e.target.value); handleFilterChange(); }}>
                <MenuItem value="">Все типы</MenuItem>
                {ANOMALY_TYPES.map((t) => <MenuItem key={t} value={t}>{labelFor(t)}</MenuItem>)}
              </Select>
            </FormControl>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 2, lg: 2 }}>
            <FormControl fullWidth size="small">
              <InputLabel>Критичность</InputLabel>
              <Select value={severity} label="Критичность" onChange={(e) => { setSeverity(e.target.value); handleFilterChange(); }}>
                <MenuItem value="">Все</MenuItem>
                {ANOMALY_SEVERITIES.map((s) => (
                  <MenuItem key={s} value={s}>{SEVERITY_LABEL[s]}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 2, lg: 2 }}>
            <FormControl fullWidth size="small">
              <InputLabel>Статус</InputLabel>
              <Select value={status} label="Статус" onChange={(e) => { setStatus(e.target.value); handleFilterChange(); }}>
                <MenuItem value="">Все</MenuItem>
                {ANOMALY_STATUSES.map((s) => (
                  <MenuItem key={s} value={s}>{STATUS_LABEL[s]}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3, lg: 2 }}>
            <TextField
              label="С"
              type="date"
              size="small"
              fullWidth
              value={dateFrom}
              onChange={(e) => { setDateFrom(e.target.value); handleFilterChange(); }}
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3, lg: 2 }}>
            <TextField
              label="По"
              type="date"
              size="small"
              fullWidth
              value={dateTo}
              onChange={(e) => { setDateTo(e.target.value); handleFilterChange(); }}
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </Grid>

          <Grid size={{ xs: 12, sm: 'auto' }}>
            <Button size="small" onClick={() => { setServerId(''); setType(''); setSeverity(''); setStatus(''); setDateFrom(''); setDateTo(''); setPage(1); }}>
              Сбросить
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      ) : isError ? (
        <Alert severity="error">Не удалось загрузить аномалии.</Alert>
      ) : anomalies.length === 0 ? (
        <Box sx={{ py: 8, textAlign: 'center' }}>
          <Typography variant="body1" color="text.secondary">
            Аномалий не найдено — система работает нормально
          </Typography>
        </Box>
      ) : (
        <>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Обнаружена</TableCell>
                  <TableCell>Сервер</TableCell>
                  <TableCell>Тип</TableCell>
                  <TableCell>Критичность</TableCell>
                  <TableCell>Статус</TableCell>
                  <TableCell>Оценка</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {anomalies.map((a) => {
                  const serverName = servers.find((s) => s.id === a.server_id)?.name ?? `#${a.server_id}`;
                  return (
                    <TableRow key={a.id} hover sx={{ cursor: 'pointer' }} onClick={() => navigate(`/anomalies/${a.id}`)}>
                      <TableCell>
                        <Typography variant="body2">{formatDate(a.detected_at)}</Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">{serverName}</Typography>
                      </TableCell>
                      <TableCell>
                        <Chip label={labelFor(a.anomaly_type)} size="small" variant="outlined" />
                      </TableCell>
                      <TableCell>
                        <Chip label={SEVERITY_LABEL[a.severity] ?? a.severity} size="small" color={SEVERITY_COLOR[a.severity] ?? 'default'} />
                      </TableCell>
                      <TableCell>
                        <Chip label={STATUS_LABEL[a.status] ?? a.status} size="small" color={STATUS_COLOR[a.status] ?? 'default'} variant="outlined" />
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {a.reconstruction_error.toFixed(4)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Button size="small" onClick={(e) => { e.stopPropagation(); navigate(`/anomalies/${a.id}`); }}>
                          Открыть
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
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
    </Box>
  );
}
