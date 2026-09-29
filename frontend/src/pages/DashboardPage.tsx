import {
  BugReport as BugIcon,
  Circle as CircleIcon,
  Notifications as NotifIcon,
  Storage as StorageIcon,
} from '@mui/icons-material';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Grid,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import type { AnomalySeverity, AnomalyStatus } from '@/entities/Anomaly';
import type { ServerStatus } from '@/entities/Server';
import { useAnomalies } from '@/features/anomalies/hooks';
import { useUnreadNotifications } from '@/features/notifications/hooks';
import { useServers } from '@/features/servers/hooks';
import { fromNow } from '@/shared/utils/formatters';

const SERVER_STATUS_COLOR: Record<ServerStatus, 'success' | 'warning' | 'error'> = {
  online: 'success',
  offline: 'error',
  degraded: 'warning',
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

function anomalyTypeLabel(type: string): string {
  return ANOMALY_TYPE_LABEL[type] ?? type.replace(/_/g, ' ');
}

interface StatCardProps {
  icon: React.ReactElement;
  label: string;
  value: number | string;
  sub?: string;
  color?: string;
  onClick?: () => void;
}

function StatCard({ icon, label, value, sub, color, onClick }: StatCardProps) {
  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2.5,
        cursor: onClick ? 'pointer' : 'default',
        '&:hover': onClick ? { bgcolor: 'action.hover' } : {},
        transition: 'background-color 0.15s',
      }}
      onClick={onClick}
    >
      <Stack direction="row" sx={{ alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <Box>
          <Typography variant="caption" color="text.secondary">{label}</Typography>
          <Typography variant="h4" sx={{ fontWeight: 700, color: color ?? 'text.primary', lineHeight: 1.2, mt: 0.5 }}>
            {value}
          </Typography>
          {sub && (
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
              {sub}
            </Typography>
          )}
        </Box>
        <Box sx={{ color: color ?? 'text.secondary', opacity: 0.7, mt: 0.5 }}>
          {icon}
        </Box>
      </Stack>
    </Paper>
  );
}

export default function DashboardPage() {
  const navigate = useNavigate();

  const { data: serversData, isLoading: serversLoading } = useServers({ limit: 200 });
  const { data: anomaliesData, isLoading: anomaliesLoading } = useAnomalies({ limit: 5 });
  const { data: unreadData } = useUnreadNotifications();

  const servers = serversData?.items ?? [];
  const recentAnomalies = anomaliesData?.items ?? [];
  const unreadCount = unreadData?.pagination?.total ?? 0;

  const onlineCount = servers.filter((s) => s.status === 'online').length;
  const offlineCount = servers.filter((s) => s.status === 'offline').length;
  const degradedCount = servers.filter((s) => s.status === 'degraded').length;
  const openAnomalies = anomaliesData?.pagination?.total ?? 0;

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 3, fontWeight: 600 }}>Дашборд</Typography>

      {}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard
            icon={<StorageIcon />}
            label="Всего серверов"
            value={servers.length}
            sub={`${onlineCount} онлайн · ${offlineCount} офлайн${degradedCount > 0 ? ` · ${degradedCount} деградация` : ''}`}
            onClick={() => navigate('/servers')}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard
            icon={<BugIcon />}
            label="Открытые аномалии"
            value={openAnomalies}
            sub={openAnomalies > 0 ? 'Требуют внимания' : 'Система в норме'}
            color={openAnomalies > 0 ? 'error.main' : undefined}
            onClick={() => navigate('/anomalies')}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard
            icon={<NotifIcon />}
            label="Непрочитанных уведомлений"
            value={unreadCount}
            sub={unreadCount > 0 ? 'Нажмите на колокольчик' : 'Всё прочитано'}
            color={unreadCount > 0 ? 'warning.main' : undefined}
            onClick={() => navigate('/notifications')}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard
            icon={<CircleIcon />}
            label="Серверов онлайн"
            value={`${onlineCount} / ${servers.length}`}
            sub={servers.length > 0 ? `${Math.round(onlineCount / servers.length * 100)}% доступность` : 'Нет серверов'}
            color={onlineCount === servers.length && servers.length > 0 ? 'success.main' : undefined}
          />
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, lg: 5 }}>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
              <Typography variant="subtitle2" color="text.secondary">Серверы</Typography>
              <Button size="small" onClick={() => navigate('/servers')}>Все серверы</Button>
            </Stack>

            {serversLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress size={24} />
              </Box>
            ) : servers.length === 0 ? (
              <Box sx={{ py: 4, textAlign: 'center' }}>
                <Typography variant="body2" color="text.secondary">Серверов пока нет</Typography>
                <Button size="small" sx={{ mt: 1 }} onClick={() => navigate('/servers')}>
                  Добавить сервер
                </Button>
              </Box>
            ) : (
              <Stack spacing={0.5}>
                {servers.slice(0, 8).map((s) => (
                  <Stack
                    key={s.id}
                    direction="row"
                    sx={{
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      p: 1,
                      borderRadius: 1,
                      cursor: 'pointer',
                      '&:hover': { bgcolor: 'action.hover' },
                    }}
                    onClick={() => navigate(`/servers/${s.id}`)}
                  >
                    <Stack direction="row" spacing={1} sx={{ alignItems: 'center', minWidth: 0 }}>
                      <CircleIcon
                        color={SERVER_STATUS_COLOR[s.status as ServerStatus] ?? 'error'}
                        sx={{ fontSize: 10, flexShrink: 0 }}
                      />
                      <Box sx={{ minWidth: 0 }}>
                        <Typography variant="body2" noWrap sx={{ fontWeight: 500 }}>
                          {s.name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" noWrap>
                          {s.host}
                        </Typography>
                      </Box>
                    </Stack>
                    <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexShrink: 0, ml: 1 }}>
                      {s.environment && (
                        <Chip label={s.environment} size="small" variant="outlined" sx={{ fontSize: '0.65rem' }} />
                      )}
                      <Typography variant="caption" color="text.disabled" sx={{ whiteSpace: 'nowrap' }}>
                        {fromNow(s.last_seen)}
                      </Typography>
                    </Stack>
                  </Stack>
                ))}
                {servers.length > 8 && (
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ pt: 0.5, textAlign: 'center', cursor: 'pointer', '&:hover': { color: 'primary.main' } }}
                    onClick={() => navigate('/servers')}
                  >
                    ещё {servers.length - 8}
                  </Typography>
                )}
              </Stack>
            )}
          </Paper>
        </Grid>

        <Grid size={{ xs: 12, lg: 7 }}>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
              <Typography variant="subtitle2" color="text.secondary">Последние аномалии</Typography>
              <Button size="small" onClick={() => navigate('/anomalies')}>Все аномалии</Button>
            </Stack>

            {anomaliesLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress size={24} />
              </Box>
            ) : recentAnomalies.length === 0 ? (
              <Box sx={{ py: 4, textAlign: 'center' }}>
                <Typography variant="body2" color="text.secondary">
                  Аномалий нет — система работает нормально
                </Typography>
              </Box>
            ) : (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Тип</TableCell>
                      <TableCell>Критичность</TableCell>
                      <TableCell>Статус</TableCell>
                      <TableCell>Сервер</TableCell>
                      <TableCell>Обнаружена</TableCell>
                      <TableCell />
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {recentAnomalies.map((a) => {
                      const serverName = servers.find((s) => s.id === a.server_id)?.name ?? `#${a.server_id}`;
                      return (
                        <TableRow
                          key={a.id}
                          hover
                          sx={{ cursor: 'pointer' }}
                          onClick={() => navigate(`/anomalies/${a.id}`)}
                        >
                          <TableCell>
                            <Typography variant="caption">{anomalyTypeLabel(a.anomaly_type)}</Typography>
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={SEVERITY_LABEL[a.severity] ?? a.severity}
                              size="small"
                              color={SEVERITY_COLOR[a.severity] ?? 'default'}
                            />
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={ANOMALY_STATUS_LABEL[a.status] ?? a.status}
                              size="small"
                              color={ANOMALY_STATUS_COLOR[a.status] ?? 'default'}
                              variant="outlined"
                            />
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption">{serverName}</Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption" color="text.secondary">
                              {fromNow(a.detected_at)}
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
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
