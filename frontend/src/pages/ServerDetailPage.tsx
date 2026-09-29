import {
  ArrowBack as ArrowBackIcon,
  Circle as CircleIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  Terminal as TerminalIcon,
  Wifi as WifiIcon,
} from '@mui/icons-material';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  Paper,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  Typography,
} from '@mui/material';
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '@/features/auth/AuthContext';
import type { ServerStatus } from '@/entities/Server';
import type { TimeRange } from '@/entities/Metric';
import type { AnomalySeverity, AnomalyStatus } from '@/entities/Anomaly';
import { useDeleteServer, useServer, useTestConnection } from '@/features/servers/hooks';
import { useAnomalies } from '@/features/anomalies/hooks';
import { formatDate, fromNow } from '@/shared/utils/formatters';
import { ContainerList } from '@/widgets/ContainerList';
import { MetricChart, TimeRangeSelector } from '@/widgets/MetricChart';
import { ServerFormDialog } from '@/widgets/ServerFormDialog';

const STATUS_COLOR: Record<ServerStatus, 'success' | 'warning' | 'error'> = {
  online: 'success',
  offline: 'error',
  degraded: 'warning',
};

const STATUS_LABEL: Record<ServerStatus, string> = {
  online: 'Онлайн',
  offline: 'Офлайн',
  degraded: 'Деградация',
};

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

const ANOMALY_STATUS_COLOR: Record<AnomalyStatus, 'error' | 'warning' | 'success' | 'default'> = {
  open: 'error',
  investigating: 'warning',
  resolved: 'success',
};

const ANOMALY_STATUS_LABEL: Record<AnomalyStatus, string> = {
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

interface TabPanelProps { children?: React.ReactNode; index: number; value: number }
function TabPanel({ children, index, value }: TabPanelProps) {
  return <Box hidden={value !== index} sx={{ pt: 2 }}>{value === index && children}</Box>;
}

function ServerAnomaliesTab({ serverId }: { serverId: number }) {
  const navigate = useNavigate();
  const { data, isLoading, isError } = useAnomalies({ server_id: serverId, limit: 50 });
  const anomalies = data?.items ?? [];

  if (isLoading) return <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress size={24} /></Box>;
  if (isError) return <Typography color="error" variant="body2">Не удалось загрузить аномалии</Typography>;
  if (anomalies.length === 0) {
    return (
      <Box sx={{ py: 4, textAlign: 'center' }}>
        <Typography variant="body2" color="text.secondary">Аномалий нет — система работает нормально</Typography>
      </Box>
    );
  }

  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Обнаружена</TableCell>
            <TableCell>Тип</TableCell>
            <TableCell>Критичность</TableCell>
            <TableCell>Статус</TableCell>
            <TableCell />
          </TableRow>
        </TableHead>
        <TableBody>
          {anomalies.map((a) => (
            <TableRow key={a.id} hover sx={{ cursor: 'pointer' }} onClick={() => navigate(`/anomalies/${a.id}`)}>
              <TableCell><Typography variant="body2">{formatDate(a.detected_at)}</Typography></TableCell>
              <TableCell>
                <Chip label={ANOMALY_TYPE_LABEL[a.anomaly_type] ?? a.anomaly_type.replace(/_/g, ' ')} size="small" variant="outlined" />
              </TableCell>
              <TableCell>
                <Chip label={SEVERITY_LABEL[a.severity] ?? a.severity} size="small" color={SEVERITY_COLOR[a.severity] ?? 'default'} />
              </TableCell>
              <TableCell>
                <Chip label={ANOMALY_STATUS_LABEL[a.status] ?? a.status} size="small" color={ANOMALY_STATUS_COLOR[a.status] ?? 'default'} variant="outlined" />
              </TableCell>
              <TableCell>
                <Button size="small" onClick={(e) => { e.stopPropagation(); navigate(`/anomalies/${a.id}`); }}>Открыть</Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

export default function ServerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const serverId = parseInt(id ?? '0', 10);
  const navigate = useNavigate();
  const { isAdmin } = useAuth();

  const { data: server, isLoading, isError } = useServer(serverId);
  const testConn = useTestConnection(serverId);
  const deleteServer = useDeleteServer();

  const [tab, setTab] = useState(0);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [timeRange, setTimeRange] = useState<TimeRange>('1h');

  if (isLoading) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}><CircularProgress /></Box>;
  }

  if (isError || !server) {
    return (
      <Box sx={{ py: 4 }}>
        <Alert severity="error">Сервер не найден.</Alert>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/servers')} sx={{ mt: 2 }}>
          К серверам
        </Button>
      </Box>
    );
  }

  const statusColor = STATUS_COLOR[server.status as ServerStatus] ?? 'error';
  const statusLabel = STATUS_LABEL[server.status as ServerStatus] ?? server.status;

  async function handleTestConnection() {
    setTestResult(null);
    const result = await testConn.mutateAsync();
    setTestResult(result);
  }

  async function handleDelete() {
    await deleteServer.mutateAsync(serverId);
    navigate('/servers');
  }

  return (
    <Box>
      <Stack direction="row" sx={{ alignItems: 'center', mb: 0.5 }} spacing={1}>
        <Button startIcon={<ArrowBackIcon />} size="small" onClick={() => navigate('/servers')} sx={{ mr: 1 }}>
          Серверы
        </Button>
      </Stack>

      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
        <Box>
          <Stack direction="row" sx={{ alignItems: 'center' }} spacing={1}>
            <Typography variant="h5">{server.name}</Typography>
            <CircleIcon color={statusColor} sx={{ fontSize: 14 }} />
            <Typography variant="body2" color="text.secondary">{statusLabel}</Typography>
          </Stack>
          <Typography variant="body2" color="text.secondary">{server.host}:{server.port}</Typography>
        </Box>

        <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <Button
            startIcon={testConn.isPending ? <CircularProgress size={14} /> : <WifiIcon />}
            variant="outlined"
            onClick={handleTestConnection}
            disabled={testConn.isPending}
          >
            Проверить
          </Button>
          <Button startIcon={<TerminalIcon />} variant="outlined" onClick={() => navigate(`/servers/${serverId}/console`)}>
            Консоль
          </Button>
          {isAdmin && (
            <>
              <Button startIcon={<EditIcon />} variant="outlined" onClick={() => setEditOpen(true)}>Изменить</Button>
              <Button startIcon={<DeleteIcon />} variant="outlined" color="error" onClick={() => setDeleteOpen(true)}>Удалить</Button>
            </>
          )}
        </Stack>
      </Stack>

      {testResult && (
        <Alert severity={testResult.success ? 'success' : 'error'} onClose={() => setTestResult(null)} sx={{ mb: 2 }}>
          {testResult.message}
        </Alert>
      )}

      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Typography variant="caption" color="text.secondary">Окружение</Typography>
            <Typography variant="body2">{server.environment ?? '—'}</Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Typography variant="caption" color="text.secondary">Последний визит</Typography>
            <Typography variant="body2">{fromNow(server.last_seen)}</Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Typography variant="caption" color="text.secondary">Добавлен</Typography>
            <Typography variant="body2">{formatDate(server.created_at)}</Typography>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Typography variant="caption" color="text.secondary">Теги</Typography>
            <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap', mt: 0.25 }}>
              {server.tags.length > 0
                ? server.tags.map((t) => <Chip key={t} label={t} size="small" />)
                : <Typography variant="body2">—</Typography>}
            </Stack>
          </Grid>
        </Grid>
      </Paper>

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tab label="Обзор" />
        <Tab label="Аномалии" />
        {isAdmin && <Tab label="Аудит" />}
      </Tabs>

      <TabPanel value={tab} index={0}>
        <Stack spacing={2}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="subtitle2" color="text.secondary">Метрики</Typography>
            <TimeRangeSelector value={timeRange} onChange={setTimeRange} />
          </Stack>

          <Grid container spacing={2}>
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper variant="outlined" sx={{ p: 2 }}>
                <MetricChart serverId={serverId} metricType="cpu_percent" timeRange={timeRange} />
              </Paper>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper variant="outlined" sx={{ p: 2 }}>
                <MetricChart serverId={serverId} metricType="memory_percent" timeRange={timeRange} />
              </Paper>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper variant="outlined" sx={{ p: 2 }}>
                <MetricChart serverId={serverId} metricType="disk_percent" timeRange={timeRange} />
              </Paper>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper variant="outlined" sx={{ p: 2 }}>
                <MetricChart serverId={serverId} metricType="network_in" timeRange={timeRange} />
              </Paper>
            </Grid>
          </Grid>

          <Divider />

          <Box>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>Контейнеры</Typography>
            <ContainerList serverId={serverId} />
          </Box>
        </Stack>
      </TabPanel>

      <TabPanel value={tab} index={1}>
        <ServerAnomaliesTab serverId={serverId} />
      </TabPanel>

      {isAdmin && (
        <TabPanel value={tab} index={2}>
          <Typography color="text.secondary">Журнал аудита для этого сервера — будет доступен позже</Typography>
        </TabPanel>
      )}

      <ServerFormDialog open={editOpen} onClose={() => setEditOpen(false)} server={server} />

      <Dialog open={deleteOpen} onClose={() => setDeleteOpen(false)}>
        <DialogTitle>Удалить сервер?</DialogTitle>
        <DialogContent>
          <Typography>
            Удалить сервер <strong>{server.name}</strong>? Это действие необратимо. Все связанные данные (метрики, аномалии) будут удалены.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteOpen(false)}>Отмена</Button>
          <Button
            color="error"
            variant="contained"
            onClick={handleDelete}
            disabled={deleteServer.isPending}
            startIcon={deleteServer.isPending ? <CircularProgress size={14} /> : null}
          >
            Удалить
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
