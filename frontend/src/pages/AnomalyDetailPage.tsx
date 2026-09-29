import {
  ArrowBack as ArrowBackIcon,
  Cancel as RejectIcon,
  CheckCircle as ApproveIcon,
  OpenInNew as OpenInNewIcon,
  Terminal as TerminalIcon,
} from '@mui/icons-material';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import { useSnackbar } from 'notistack';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { AnomalySeverity, AnomalyStatus } from '@/entities/Anomaly';
import type { RecommendationStatus } from '@/entities/Recommendation';
import { useAuth } from '@/features/auth/AuthContext';
import {
  useAnomaly,
  useAnomalyRecommendations,
  useApproveRecommendation,
  useRejectRecommendation,
  useUpdateAnomalyStatus,
} from '@/features/anomalies/hooks';
import { useServer } from '@/features/servers/hooks';
import { ApiError } from '@/shared/api/types';
import { copyToClipboard } from '@/shared/utils/clipboard';
import { formatDate, fromNow } from '@/shared/utils/formatters';

const SEVERITY_COLOR: Record<AnomalySeverity, 'default' | 'info' | 'warning' | 'error'> = {
  low: 'info',
  medium: 'warning',
  high: 'error',
  critical: 'error',
};

const STATUS_COLOR: Record<AnomalyStatus, 'error' | 'warning' | 'success' | 'default'> = {
  open: 'error',
  investigating: 'warning',
  resolved: 'success',
};

const REC_STATUS_COLOR: Record<RecommendationStatus, 'default' | 'warning' | 'success' | 'error' | 'info'> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'error',
  executed: 'info',
  failed: 'error',
};

const SEVERITY_LABEL: Record<AnomalySeverity, string> = {
  low: 'Низкая',
  medium: 'Средняя',
  high: 'Высокая',
  critical: 'Критическая',
};

const STATUS_LABEL: Record<AnomalyStatus, string> = {
  open: 'Открыта',
  investigating: 'Изучается',
  resolved: 'Решена',
};

function labelFor(type: string): string {
  return type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(Math.abs(bytes)) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[Math.min(i, sizes.length - 1)]}`;
}

function formatCompact(n: number): string {
  if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return n.toFixed(3);
}

interface MetricMeta {
  label: string;
  format: (v: number) => string;
  description: string;
}

const METRIC_META: Record<string, MetricMeta> = {
  cpu_percent: {
    label: 'Загрузка CPU',
    format: (v) => `${v.toFixed(1)}%`,
    description: 'Процент использования CPU всех ядер',
  },
  memory_percent: {
    label: 'Использование памяти',
    format: (v) => `${v.toFixed(1)}%`,
    description: 'Процент использования оперативной памяти',
  },
  disk_percent: {
    label: 'Использование диска',
    format: (v) => `${v.toFixed(1)}%`,
    description: 'Процент использования дискового пространства',
  },
  load_average_1m: {
    label: 'Нагрузка (1 мин)',
    format: (v) => v.toFixed(2),
    description: 'Среднее количество запущенных процессов за последнюю минуту',
  },
  load_average_5m: {
    label: 'Нагрузка (5 мин)',
    format: (v) => v.toFixed(2),
    description: 'Среднее количество запущенных процессов за последние 5 минут',
  },
  load_average_15m: {
    label: 'Нагрузка (15 мин)',
    format: (v) => v.toFixed(2),
    description: 'Среднее количество запущенных процессов за последние 15 минут',
  },
  network_in_bytes: {
    label: 'Входящий трафик',
    format: formatBytes,
    description: 'Всего байт получено с последнего сбора метрик',
  },
  network_out_bytes: {
    label: 'Исходящий трафик',
    format: formatBytes,
    description: 'Всего байт отправлено с последнего сбора метрик',
  },
  process_count: {
    label: 'Процессы',
    format: (v) => String(Math.round(v)),
    description: 'Общее количество запущенных процессов',
  },
  active_connections: {
    label: 'Активные подключения',
    format: (v) => String(Math.round(v)),
    description: 'Количество активных сетевых подключений',
  },
  disk_read_bytes: {
    label: 'Чтение с диска',
    format: formatBytes,
    description: 'Байт прочитано с диска с последнего сбора метрик',
  },
  disk_write_bytes: {
    label: 'Запись на диск',
    format: formatBytes,
    description: 'Байт записано на диск с последнего сбора метрик',
  },
  swap_used_mb: {
    label: 'Использование swap',
    format: (v) => `${v.toFixed(0)} MB`,
    description: 'Количество используемого swap-пространства',
  },
};

function formatMetricValue(key: string, val: unknown): string {
  if (key === 'collected_at') return formatDate(String(val));
  if (typeof val !== 'number') return String(val);
  const meta = METRIC_META[key];
  return meta ? meta.format(val) : val.toFixed(2);
}

function metricLabel(key: string): string {
  return METRIC_META[key]?.label ?? key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function metricDescription(key: string): string {
  return METRIC_META[key]?.description ?? '';
}

// ─── SHAP ────────────────────────────────────────────────────────────────────

interface ShapEntry { feature: string; value: number; abs: number }

type ShapPayload = Record<string, number> | Array<{ metric: string; impact_percent: number }>;

function normalizeShap(data: ShapPayload | undefined | null): ShapEntry[] {
  if (!data) return [];
  if (Array.isArray(data)) {
    return data
      .map((item) => ({
        feature: String(item.metric),
        value: Number(item.impact_percent) / 100,
        abs: Math.abs(Number(item.impact_percent) / 100),
      }))
      .sort((a, b) => b.abs - a.abs)
      .slice(0, 12);
  }
  return Object.entries(data)
    .map(([feature, value]) => ({ feature, value: Number(value), abs: Math.abs(Number(value)) }))
    .sort((a, b) => b.abs - a.abs)
    .slice(0, 12);
}

function ShapChart({ data }: { data: ShapPayload }) {
  const entries = normalizeShap(data);

  if (entries.length === 0) {
    return <Typography variant="body2" color="text.secondary">Данные SHAP недоступны</Typography>;
  }

  return (
    <ResponsiveContainer width="100%" height={Math.max(200, entries.length * 30)}>
      <BarChart data={entries} layout="vertical" margin={{ left: 16, right: 48, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
        <XAxis
          type="number"
          tickFormatter={(v: unknown) => Number(v).toFixed(2)}
          label={{ value: 'SHAP-значение (влияние на оценку аномалии)', position: 'insideBottom', offset: -2, fontSize: 11 }}
          height={36}
        />
        <YAxis
          type="category"
          dataKey="feature"
          width={140}
          tick={{ fontSize: 12 }}
          tickFormatter={(v: unknown) => String(v).replace(/_/g, ' ')}
        />
        <ChartTooltip
          formatter={(value: unknown) => [`${Number(value).toFixed(4)}`, 'Вклад SHAP']}
          labelFormatter={(label: unknown) => `Признак: ${String(label).replace(/_/g, ' ')}`}
          contentStyle={{ fontSize: 12 }}
        />
        <Bar dataKey="value" name="SHAP value" radius={[0, 3, 3, 0]}>
          {entries.map((entry, index) => (
            <Cell key={index} fill={entry.value >= 0 ? '#f44336' : '#4caf50'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function AnomalyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const anomalyId = parseInt(id ?? '0', 10);
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const { enqueueSnackbar } = useSnackbar();

  const { data: anomaly, isLoading, isError } = useAnomaly(anomalyId);
  const { data: server } = useServer(anomaly?.server_id);
  const { data: recommendations = [] } = useAnomalyRecommendations(anomalyId);
  const updateStatus = useUpdateAnomalyStatus(anomalyId);
  const approve = useApproveRecommendation(anomalyId);
  const reject = useRejectRecommendation(anomalyId);

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (isError || !anomaly) {
    return (
      <Box sx={{ py: 4 }}>
        <Alert severity="error">Аномалия не найдена.</Alert>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/anomalies')} sx={{ mt: 2 }}>
          К аномалиям
        </Button>
      </Box>
    );
  }

  async function handleStatusChange(newStatus: string) {
    try {
      await updateStatus.mutateAsync(newStatus);
      enqueueSnackbar('Статус обновлён', { variant: 'success' });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Не удалось обновить статус';
      enqueueSnackbar(msg, { variant: 'error' });
    }
  }

  async function handleApprove(recId: number) {
    try {
      await approve.mutateAsync(recId);
      enqueueSnackbar('Рекомендация одобрена', { variant: 'success' });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Не удалось одобрить';
      enqueueSnackbar(msg, { variant: 'error' });
    }
  }

  async function handleReject(recId: number) {
    try {
      await reject.mutateAsync(recId);
      enqueueSnackbar('Рекомендация отклонена', { variant: 'success' });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Не удалось отклонить';
      enqueueSnackbar(msg, { variant: 'error' });
    }
  }

  const shapData = anomaly.shap_explanation ?? {};
  const metricsSnap = anomaly.metrics_snapshot ?? {};
  const metricEntries = Object.entries(metricsSnap).filter(([k]) => k !== 'collected_at');
  const collectedAt = metricsSnap['collected_at'] as string | undefined;

  const ratio = anomaly.threshold > 0 ? anomaly.reconstruction_error / anomaly.threshold : null;

  return (
    <Box>
      <Button startIcon={<ArrowBackIcon />} size="small" onClick={() => navigate('/anomalies')} sx={{ mb: 1 }}>
        Аномалии
      </Button>

      <Stack
        direction="row"
        sx={{ justifyContent: 'space-between', alignItems: 'flex-start', mb: 2, flexWrap: 'wrap', gap: 1 }}
      >
        <Box>
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 0.5 }}>
            <Chip
              label={SEVERITY_LABEL[anomaly.severity] ?? anomaly.severity}
              color={SEVERITY_COLOR[anomaly.severity] ?? 'default'}
              sx={{ fontWeight: 700 }}
            />
            <Chip
              label={STATUS_LABEL[anomaly.status] ?? anomaly.status}
              size="small"
              color={STATUS_COLOR[anomaly.status] ?? 'default'}
              variant="outlined"
            />
            <Typography variant="h6">{labelFor(anomaly.anomaly_type)}</Typography>
          </Stack>

          <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center' }}>
            {server ? (
              <Button
                size="small"
                endIcon={<OpenInNewIcon sx={{ fontSize: '0.9rem !important' }} />}
                onClick={() => navigate(`/servers/${anomaly.server_id}`)}
                sx={{ p: 0, minWidth: 0, textTransform: 'none', color: 'text.secondary', fontWeight: 400 }}
              >
                {server.name}
              </Button>
            ) : (
              <Typography variant="body2" color="text.secondary">Сервер #{anomaly.server_id}</Typography>
            )}
            <Typography variant="body2" color="text.secondary">·</Typography>
            <Tooltip title={formatDate(anomaly.detected_at)} placement="right">
              <Typography variant="body2" color="text.secondary" sx={{ cursor: 'default' }}>
                Обнаружена {fromNow(anomaly.detected_at)}
              </Typography>
            </Tooltip>
            {anomaly.resolved_at && (
              <>
                <Typography variant="body2" color="text.secondary">·</Typography>
                <Typography variant="body2" color="success.main">
                  Решена {fromNow(anomaly.resolved_at)}
                </Typography>
              </>
            )}
          </Stack>
        </Box>

        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Статус</InputLabel>
          <Select
            value={anomaly.status}
            label="Статус"
            disabled={updateStatus.isPending}
            onChange={(e) => handleStatusChange(e.target.value)}
          >
            <MenuItem value="open">Открыта</MenuItem>
            <MenuItem value="investigating">Изучается</MenuItem>
            <MenuItem value="resolved">Решена</MenuItem>
          </Select>
        </FormControl>
      </Stack>

      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>
          Оценки обнаружения
        </Typography>
        <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mb: 1.5 }}>
          ML-модель восстанавливает нормальные паттерны метрик. Высокая ошибка реконструкции означает,
          что текущее состояние значительно отличается от изученной нормы.
        </Typography>
        <Stack direction="row" spacing={4} sx={{ flexWrap: 'wrap', gap: 2 }}>
          <Tooltip title="Насколько текущие метрики отличаются от нормального паттерна модели" placement="top">
            <Box sx={{ cursor: 'help' }}>
              <Typography variant="caption" color="text.secondary">Ошибка реконструкции</Typography>
              <Typography variant="body1" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                {formatCompact(anomaly.reconstruction_error)}
              </Typography>
            </Box>
          </Tooltip>
          <Tooltip title="Максимальная ошибка реконструкции, считающаяся нормой (обучена на исторических данных)" placement="top">
            <Box sx={{ cursor: 'help' }}>
              <Typography variant="caption" color="text.secondary">Нормальный порог</Typography>
              <Typography variant="body1" sx={{ fontFamily: 'monospace' }}>
                {formatCompact(anomaly.threshold)}
              </Typography>
            </Box>
          </Tooltip>
          {ratio !== null && (
            <Tooltip title={`Ошибка превышает нормальный порог в ${ratio.toFixed(0)}×`} placement="top">
              <Box sx={{ cursor: 'help' }}>
                <Typography variant="caption" color="text.secondary">Превышение порога</Typography>
                <Typography variant="body1" sx={{ fontFamily: 'monospace', color: 'error.main', fontWeight: 700 }}>
                  {ratio >= 1000 ? `×${formatCompact(ratio)}` : `×${ratio.toFixed(1)}`}
                </Typography>
              </Box>
            </Tooltip>
          )}
        </Stack>
      </Paper>

      {metricEntries.length > 0 && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'baseline', mb: 1.5 }}>
            <Box>
              <Typography variant="subtitle2" color="text.secondary">
                Метрики на момент обнаружения
              </Typography>
              <Typography variant="caption" color="text.disabled">
                Состояние сервера на момент обнаружения аномалии
              </Typography>
            </Box>
            {collectedAt && (
              <Typography variant="caption" color="text.disabled">
                Собрано {formatDate(collectedAt)}
              </Typography>
            )}
          </Stack>
          <Grid container spacing={2}>
            {metricEntries.map(([key, val]) => {
              const desc = metricDescription(key);
              return (
                <Grid key={key} size={{ xs: 6, sm: 4, md: 3, lg: 2 }}>
                  <Tooltip title={desc || undefined} placement="top" disableHoverListener={!desc}>
                    <Box sx={{ cursor: desc ? 'help' : 'default' }}>
                      <Typography variant="caption" color="text.secondary" noWrap>
                        {metricLabel(key)}
                      </Typography>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                        {formatMetricValue(key, val)}
                      </Typography>
                    </Box>
                  </Tooltip>
                </Grid>
              );
            })}
          </Grid>
        </Paper>
      )}

      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>
          Важность признаков (SHAP)
        </Typography>
        <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mb: 2 }}>
          Показывает, какие метрики больше всего способствовали обнаружению этой аномалии.
          Красные полосы увеличивают оценку (в сторону аномалии), зелёные — уменьшают (в сторону нормы).
          Чем длиннее полоса, тем сильнее влияние.
        </Typography>
        <ShapChart data={shapData} />
      </Paper>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>
          Рекомендации
        </Typography>
        <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mb: 2 }}>
          Шаги по устранению, сгенерированные ИИ на основе обнаруженного паттерна аномалии
        </Typography>

        {recommendations.length === 0 ? (
          <Typography variant="body2" color="text.secondary">Пока нет рекомендаций</Typography>
        ) : (
          <Stack spacing={2} divider={<Divider />}>
            {recommendations.map((rec) => {
              const isPending = rec.status === 'pending';
              const actionPending = approve.isPending || reject.isPending;
              return (
                <Box key={rec.id}>
                  <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                    <Chip
                      label={rec.status}
                      size="small"
                      color={REC_STATUS_COLOR[rec.status] ?? 'default'}
                      sx={{ textTransform: 'capitalize' }}
                    />
                    <Typography variant="caption" color="text.secondary">
                      {formatDate(rec.created_at)}
                    </Typography>
                  </Stack>

                  <Typography variant="body2" sx={{ mb: 1 }}>
                    {rec.explanation}
                  </Typography>

                  <Box
                    component="pre"
                    sx={{
                      p: 1.5,
                      mb: 1,
                      bgcolor: 'action.hover',
                      borderRadius: 1,
                      fontFamily: 'monospace',
                      fontSize: '0.8rem',
                      overflowX: 'auto',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                    }}
                  >
                    {rec.filtered_command}
                  </Box>

                  <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
                    {isAdmin && isPending && (
                      <>
                        <Button
                          startIcon={actionPending ? <CircularProgress size={14} /> : <ApproveIcon />}
                          variant="contained"
                          color="success"
                          size="small"
                          disabled={actionPending}
                          onClick={() => handleApprove(rec.id)}
                        >
                          Одобрить
                        </Button>
                        <Button
                          startIcon={actionPending ? <CircularProgress size={14} /> : <RejectIcon />}
                          variant="outlined"
                          color="error"
                          size="small"
                          disabled={actionPending}
                          onClick={() => handleReject(rec.id)}
                        >
                          Отклонить
                        </Button>
                      </>
                    )}
                    {rec.filtered_command && (
                      <Button
                        startIcon={<TerminalIcon />}
                        variant="outlined"
                        size="small"
                        onClick={async () => {
                          const ok = await copyToClipboard(rec.filtered_command);
                          if (ok) {
                            enqueueSnackbar('Команда скопирована в буфер обмена', {
                              variant: 'success',
                            });
                          }
                          navigate(`/servers/${anomaly.server_id}/console`);
                        }}
                      >
                        Открыть в консоли
                      </Button>
                    )}
                  </Stack>

                  {rec.execution_result && Object.keys(rec.execution_result).length > 0 && (
                    <Box sx={{ mt: 1 }}>
                      <Typography variant="caption" color="text.secondary">Результат выполнения:</Typography>
                      <Box
                        component="pre"
                        sx={{
                          p: 1,
                          bgcolor: 'action.hover',
                          borderRadius: 1,
                          fontFamily: 'monospace',
                          fontSize: '0.75rem',
                          overflowX: 'auto',
                          whiteSpace: 'pre-wrap',
                          mt: 0.5,
                        }}
                      >
                        {JSON.stringify(rec.execution_result, null, 2)}
                      </Box>
                    </Box>
                  )}
                </Box>
              );
            })}
          </Stack>
        )}
      </Paper>
    </Box>
  );
}
