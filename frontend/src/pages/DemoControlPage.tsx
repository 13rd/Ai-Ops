import { useEffect, useRef, useState } from 'react';
import {
  BugReport as BugReportIcon,
  CloudOff as CloudOffIcon,
  Memory as MemoryIcon,
  NetworkCheck as NetworkIcon,
  PlayArrow as PlayIcon,
  Refresh as RefreshIcon,
  Stop as StopIcon,
  Storage as StorageIcon,
  Speed as SpeedIcon,
  Videocam as ContainerIcon,
} from '@mui/icons-material';
import {
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Typography,
} from '@mui/material';
import { useSnackbar } from 'notistack';
import apiClient from '@/shared/api/client';

interface ServerInfo {
  id: number;
  name: string;
  host: string;
  status: string;
  synthetic: boolean;
  open_anomalies: number;
  latest_metric: string | null;
}

interface StatusResponse {
  demo_mode: boolean;
  servers: ServerInfo[];
}

interface AnomalyType {
  key: string;
  label: string;
  icon: React.ReactElement;
  color: 'error' | 'warning' | 'info' | 'secondary';
}

const ANOMALY_TYPES: AnomalyType[] = [
  { key: 'cpu_spike',       label: 'CPU Spike',       icon: <SpeedIcon />,     color: 'error' },
  { key: 'memory_leak',     label: 'Memory Leak',     icon: <MemoryIcon />,    color: 'warning' },
  { key: 'disk_fill',       label: 'Disk Fill',       icon: <StorageIcon />,   color: 'warning' },
  { key: 'network_storm',   label: 'Network Storm',   icon: <NetworkIcon />,   color: 'info' },
  { key: 'service_down',    label: 'Service Down',    icon: <CloudOffIcon />,  color: 'error' },
  { key: 'container_crash', label: 'Container Crash', icon: <ContainerIcon />, color: 'secondary' },
];

interface LogEntry {
  ts: string;
  msg: string;
  ok: boolean;
}

export default function DemoControlPage() {
  const { enqueueSnackbar } = useSnackbar();
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [selectedServer, setSelectedServer] = useState<number | ''>('');
  const [activeType, setActiveType] = useState<string | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  const addLog = (msg: string, ok = true) => {
    const ts = new Date().toLocaleTimeString('ru-RU');
    setLog((prev) => [...prev.slice(-49), { ts, msg, ok }]);
  };

  const fetchStatus = async () => {
    try {
      const res = await apiClient.get<StatusResponse>('/demo/status');
      const data = res.data;
      setStatus(data);
      if (!selectedServer && data.servers.length > 0) {
        const real = data.servers.find((s) => !s.synthetic) ?? data.servers[0];
        setSelectedServer(real.id);
      }
    } catch {
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [log]);

  const post = async (path: string, label: string) => {
    if (!selectedServer) {
      enqueueSnackbar('Выберите сервер', { variant: 'warning' });
      return;
    }
    setLoading(true);
    try {
      const res = await apiClient.post<Record<string, unknown>>(
        `/demo${path}?server_id=${selectedServer}`
      );
      addLog(`${label}: ${JSON.stringify(res.data)}`);
      enqueueSnackbar(label, { variant: 'success' });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      addLog(`${label} FAILED: ${msg}`, false);
      enqueueSnackbar(`Ошибка: ${msg}`, { variant: 'error' });
    } finally {
      setLoading(false);
      fetchStatus();
    }
  };

  const handleTrigger = (type: string) => {
    setActiveType(type);
    post(`/trigger/${type}`, `Trigger ${type}`);
  };

  const handleStop = () => {
    setActiveType(null);
    post('/stop', 'Stop anomaly');
  };

  const handleRunML = () => post('/run-ml', 'Run ML now');

  const currentServer = status?.servers.find((s) => s.id === selectedServer);

  return (
    <Box>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 3 }}>
        <BugReportIcon color="error" fontSize="large" />
        <Typography variant="h5" sx={{ fontWeight: 700 }}>
          Demo Control Panel
        </Typography>
        <Chip label="DEMO MODE" color="error" size="small" sx={{ ml: 1 }} />
      </Stack>

      <Alert severity="info" sx={{ mb: 3 }}>
        Этот раздел виден только в demo-режиме. Используйте кнопки ниже, чтобы инициировать
        аномалию на реальном сервере через SSH, а затем запустить ML-анализ.
      </Alert>

      <Paper sx={{ p: 2, mb: 3 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 220 }}>
            <InputLabel>Целевой сервер</InputLabel>
            <Select
              value={selectedServer}
              label="Целевой сервер"
              onChange={(e) => setSelectedServer(e.target.value as number)}
            >
              {(status?.servers ?? []).map((s) => (
                <MenuItem key={s.id} value={s.id}>
                  {s.name}
                  {s.synthetic ? ' (синт.)' : ''} — {s.status}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {currentServer && (
            <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
              <Chip
                label={currentServer.status}
                color={currentServer.status === 'online' ? 'success' : 'default'}
                size="small"
              />
              <Chip label={currentServer.host} size="small" variant="outlined" />
              {currentServer.open_anomalies > 0 && (
                <Chip
                  label={`${currentServer.open_anomalies} открытых аномалий`}
                  color="warning"
                  size="small"
                />
              )}
              {activeType && (
                <Chip label={`Активно: ${activeType}`} color="error" size="small" />
              )}
            </Stack>
          )}

          <Button
            size="small"
            startIcon={<RefreshIcon />}
            onClick={fetchStatus}
            sx={{ ml: 'auto' }}
          >
            Обновить
          </Button>
        </Stack>
      </Paper>

      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1.5 }}>
        Инъекция аномалии
      </Typography>
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: {
            xs: 'repeat(2, 1fr)',
            sm: 'repeat(3, 1fr)',
            md: 'repeat(6, 1fr)',
          },
          gap: 2,
          mb: 3,
        }}
      >
        {ANOMALY_TYPES.map((t) => (
          <Button
            key={t.key}
            fullWidth
            variant={activeType === t.key ? 'contained' : 'outlined'}
            color={t.color}
            startIcon={t.icon}
            disabled={loading || currentServer?.synthetic}
            onClick={() => handleTrigger(t.key)}
            sx={{ flexDirection: 'column', py: 1.5, gap: 0.5, height: 80 }}
          >
            <Box sx={{ fontSize: 11, lineHeight: 1.2, textAlign: 'center' }}>{t.label}</Box>
          </Button>
        ))}
      </Box>

      {currentServer?.synthetic && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Выбранный сервер синтетический — SSH-инъекция недоступна. Выберите реальный сервер.
        </Alert>
      )}

      <Divider sx={{ my: 2 }} />
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ mb: 3 }}>
        <Button
          variant="contained"
          color="primary"
          startIcon={<PlayIcon />}
          disabled={loading}
          onClick={handleRunML}
          size="large"
        >
          Запустить ML сейчас
        </Button>
        <Button
          variant="outlined"
          color="inherit"
          startIcon={<StopIcon />}
          disabled={loading || currentServer?.synthetic}
          onClick={handleStop}
          size="large"
        >
          Остановить аномалию
        </Button>
      </Stack>

      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
        Журнал событий
      </Typography>
      <Paper
        variant="outlined"
        sx={{
          p: 1.5,
          maxHeight: 240,
          overflowY: 'auto',
          fontFamily: 'monospace',
          fontSize: 12,
          bgcolor: 'grey.900',
          color: 'grey.100',
        }}
      >
        {log.length === 0 ? (
          <Typography variant="caption" color="grey.500">
            Событий пока нет...
          </Typography>
        ) : (
          log.map((entry, i) => (
            <Box key={i} sx={{ color: entry.ok ? 'success.light' : 'error.light', mb: 0.5 }}>
              [{entry.ts}] {entry.msg}
            </Box>
          ))
        )}
        <div ref={logEndRef} />
      </Paper>
    </Box>
  );
}
