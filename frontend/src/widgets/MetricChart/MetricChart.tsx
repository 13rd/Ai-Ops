import { Box, CircularProgress, Typography, useTheme } from '@mui/material';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';

dayjs.extend(utc);
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { MetricTypeName, TimeRange } from '@/entities/Metric';
import { useHistoricalMetric } from '@/features/metrics/hooks';

interface MetricConfig {
  label: string;
  unit: string;
  color: string;
  threshold?: number;
  domain: [number | 'auto', number | 'auto'];
  formatValue: (v: number) => string;
}

const METRIC_CONFIG: Record<string, MetricConfig> = {
  cpu_percent: {
    label: 'Загрузка CPU',
    unit: '%',
    color: '#00bcd4',
    threshold: 90,
    domain: [0, 100],
    formatValue: (v) => `${v.toFixed(1)}%`,
  },
  memory_percent: {
    label: 'Использование памяти',
    unit: '%',
    color: '#9c27b0',
    threshold: 90,
    domain: [0, 100],
    formatValue: (v) => `${v.toFixed(1)}%`,
  },
  disk_percent: {
    label: 'Использование диска',
    unit: '%',
    color: '#ff9800',
    threshold: 85,
    domain: [0, 100],
    formatValue: (v) => `${v.toFixed(1)}%`,
  },
  network_in: {
    label: 'Входящий трафик',
    unit: 'Б/с',
    color: '#4caf50',
    domain: [0, 'auto'],
    formatValue: formatBytes,
  },
  network_out: {
    label: 'Исходящий трафик',
    unit: 'Б/с',
    color: '#f44336',
    domain: [0, 'auto'],
    formatValue: formatBytes,
  },
  load_average_1m: {
    label: 'Нагрузка (1 мин)',
    unit: '',
    color: '#2196f3',
    domain: [0, 'auto'],
    formatValue: (v) => v.toFixed(2),
  },
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes.toFixed(0)} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

function xTickFormatter(ts: string, timeRange: TimeRange): string {
  const d = dayjs.utc(ts).local();
  if (timeRange === '1h' || timeRange === '24h') return d.format('HH:mm');
  return d.format('DD.MM');
}

interface Props {
  serverId: number;
  metricType: MetricTypeName;
  timeRange: TimeRange;
  height?: number;
}

export function MetricChart({ serverId, metricType, timeRange, height = 180 }: Props) {
  const theme = useTheme();
  const gridStroke = theme.palette.divider;
  const axisFill = theme.palette.text.secondary;
  const { data, isLoading, isError } = useHistoricalMetric(serverId, metricType, timeRange);
  const cfg = METRIC_CONFIG[metricType] ?? {
    label: metricType,
    unit: '',
    color: '#00bcd4',
    domain: [0, 'auto'] as [number, 'auto'],
    formatValue: (v: number) => v.toFixed(2),
  };

  const chartData = data?.metrics.map((m) => ({ ts: m.timestamp, value: m.value_avg ?? null })) ?? [];

  return (
    <Box>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
        {cfg.label}{cfg.unit ? ` (${cfg.unit})` : ''}
      </Typography>

      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height }}>
          <CircularProgress size={24} />
        </Box>
      )}

      {isError && (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height }}>
          <Typography variant="caption" color="error">Не удалось загрузить метрики</Typography>
        </Box>
      )}

      {!isLoading && !isError && chartData.length === 0 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height }}>
          <Typography variant="caption" color="text.secondary">Данных за этот период нет</Typography>
        </Box>
      )}

      {!isLoading && !isError && chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={height}>
          <AreaChart data={chartData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
            <defs>
              <linearGradient id={`grad-${metricType}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={cfg.color} stopOpacity={0.3} />
                <stop offset="95%" stopColor={cfg.color} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
            <XAxis
              dataKey="ts"
              tickFormatter={(ts: string) => xTickFormatter(ts, timeRange)}
              tick={{ fontSize: 10, fill: axisFill }}
              tickLine={false}
              axisLine={false}
              minTickGap={40}
            />
            <YAxis
              domain={cfg.domain}
              tick={{ fontSize: 10, fill: axisFill }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) =>
                cfg.unit === '%' ? `${v}%` : v >= 1024 * 1024 ? `${(v / (1024 * 1024)).toFixed(0)}М` : v >= 1024 ? `${(v / 1024).toFixed(0)}К` : String(v)
              }
            />
            <Tooltip
              contentStyle={{
                background: theme.palette.background.paper,
                border: `1px solid ${theme.palette.divider}`,
                borderRadius: 4,
              }}
              labelStyle={{ color: theme.palette.text.secondary, fontSize: 11 }}
              itemStyle={{ fontSize: 11, color: theme.palette.text.primary }}
              labelFormatter={(ts: unknown) => typeof ts === 'string' ? dayjs.utc(ts).local().format('DD.MM.YYYY HH:mm') : String(ts)}
              formatter={(value: unknown) => {
                const v = typeof value === 'number' ? value : null;
                return v != null ? cfg.formatValue(v) : '—';
              }}
            />
            {cfg.threshold != null && (
              <ReferenceLine
                y={cfg.threshold}
                stroke="#f44336"
                strokeDasharray="4 4"
                strokeWidth={1}
                label={{ value: `${cfg.threshold}%`, fill: '#f44336', fontSize: 10, position: 'insideTopRight' }}
              />
            )}
            <Area
              type="monotone"
              dataKey="value"
              stroke={cfg.color}
              strokeWidth={1.5}
              fill={`url(#grad-${metricType})`}
              dot={false}
              activeDot={{ r: 3, fill: cfg.color }}
              connectNulls={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </Box>
  );
}
