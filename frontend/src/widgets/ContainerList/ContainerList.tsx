import {
  Delete as DeleteIcon,
  PlayArrow as StartIcon,
  ReceiptLong as LogsIcon,
  Refresh as RestartIcon,
  Stop as StopIcon,
} from '@mui/icons-material';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import { useSnackbar } from 'notistack';
import { useState } from 'react';
import type { ContainerAction, ContainerSnapshot } from '@/entities/Container';
import { useAuth } from '@/features/auth/AuthContext';
import { useContainerAction, useContainers, useDeleteContainer } from '@/features/containers/hooks';
import { useMyServerAccess } from '@/features/servers/hooks';
import { ApiError } from '@/shared/api/types';
import { ContainerLogsDrawer } from './ContainerLogsDrawer';

function statusColor(status: string | null): 'success' | 'error' | 'warning' | 'default' {
  if (!status) return 'default';
  const s = status.toLowerCase();
  if (s === 'running') return 'success';
  if (s === 'exited' || s === 'dead') return 'error';
  if (s === 'paused' || s === 'restarting') return 'warning';
  return 'default';
}

function statusLabel(status: string | null): string {
  if (!status) return 'неизвестно';
  const map: Record<string, string> = {
    running: 'запущен',
    exited: 'остановлен',
    dead: 'упал',
    paused: 'на паузе',
    restarting: 'перезапуск',
  };
  return map[status.toLowerCase()] ?? status;
}

function fmt(v: number | null | undefined, decimals = 1, unit = ''): string {
  if (v == null) return '—';
  return `${v.toFixed(decimals)}${unit}`;
}

const ACTION_LABEL: Record<ContainerAction | 'delete', string> = {
  start: 'Запустить',
  stop: 'Остановить',
  restart: 'Перезапустить',
  delete: 'Удалить',
};

interface ConfirmState { containerId: string; containerName: string; action: ContainerAction | 'delete' }

interface Props { serverId: number }

export function ContainerList({ serverId }: Props) {
  const { isAdmin } = useAuth();
  const { data: myAccess } = useMyServerAccess(serverId);
  const canControl = isAdmin || myAccess?.permission === 'write';
  const { data: containers, isLoading, isError } = useContainers(serverId);
  const containerAction = useContainerAction(serverId);
  const deleteContainer = useDeleteContainer(serverId);
  const { enqueueSnackbar } = useSnackbar();
  const [confirm, setConfirm] = useState<ConfirmState | null>(null);
  const [logsTarget, setLogsTarget] = useState<ContainerSnapshot | null>(null);

  async function handleConfirm() {
    if (!confirm) return;
    try {
      if (confirm.action === 'delete') {
        await deleteContainer.mutateAsync({ containerId: confirm.containerId });
        enqueueSnackbar('Контейнер удалён', { variant: 'success' });
      } else {
        await containerAction.mutateAsync({ containerId: confirm.containerId, action: confirm.action });
        enqueueSnackbar(`Операция выполнена`, { variant: 'success' });
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Ошибка операции';
      enqueueSnackbar(msg, { variant: 'error' });
    } finally {
      setConfirm(null);
    }
  }

  function openConfirm(c: ContainerSnapshot, action: ContainerAction | 'delete') {
    setConfirm({ containerId: c.container_id, containerName: c.container_name, action });
  }

  if (isLoading) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress size={24} /></Box>;
  }

  if (isError) {
    return <Typography variant="body2" color="error" sx={{ py: 2 }}>Не удалось загрузить контейнеры</Typography>;
  }

  if (!containers || containers.length === 0) {
    return (
      <Box sx={{ py: 4, textAlign: 'center' }}>
        <Typography variant="body2" color="text.secondary">Контейнеров на этом сервере нет</Typography>
      </Box>
    );
  }

  const isPending = containerAction.isPending || deleteContainer.isPending;

  return (
    <>
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Название</TableCell>
              <TableCell>Образ</TableCell>
              <TableCell>Статус</TableCell>
              <TableCell>CPU%</TableCell>
              <TableCell>Память</TableCell>
              <TableCell>Рестарты</TableCell>
              {canControl && <TableCell align="right">Действия</TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {containers.map((c) => (
              <TableRow key={c.container_id} hover>
                <TableCell>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{c.container_name}</Typography>
                  {c.ports && <Typography variant="caption" color="text.secondary">{c.ports}</Typography>}
                </TableCell>
                <TableCell>
                  <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace' }}>{c.image ?? '—'}</Typography>
                </TableCell>
                <TableCell>
                  <Chip label={statusLabel(c.status)} color={statusColor(c.status)} size="small" variant="outlined" />
                </TableCell>
                <TableCell>{fmt(c.cpu_percentage, 1, '%')}</TableCell>
                <TableCell>
                  {c.memory_usage_mb != null ? `${c.memory_usage_mb.toFixed(0)} МБ` : '—'}
                  {c.memory_percentage != null && (
                    <Typography variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
                      ({c.memory_percentage.toFixed(1)}%)
                    </Typography>
                  )}
                </TableCell>
                <TableCell>{c.restart_count ?? '—'}</TableCell>
                {canControl && (
                  <TableCell align="right">
                    <Stack direction="row" spacing={0.5} sx={{ justifyContent: 'flex-end' }}>
                      <Tooltip title="Логи">
                        <IconButton size="small" onClick={() => setLogsTarget(c)}>
                          <LogsIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Запустить">
                        <span>
                          <IconButton size="small" color="success" disabled={isPending || c.running === true} onClick={() => openConfirm(c, 'start')}>
                            <StartIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Tooltip title="Остановить">
                        <span>
                          <IconButton size="small" color="warning" disabled={isPending || c.running === false} onClick={() => openConfirm(c, 'stop')}>
                            <StopIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Tooltip title="Перезапустить">
                        <span>
                          <IconButton size="small" color="info" disabled={isPending} onClick={() => openConfirm(c, 'restart')}>
                            <RestartIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Tooltip title="Удалить">
                        <span>
                          <IconButton size="small" color="error" disabled={isPending} onClick={() => openConfirm(c, 'delete')}>
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                    </Stack>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {logsTarget && (
        <ContainerLogsDrawer
          open={!!logsTarget}
          onClose={() => setLogsTarget(null)}
          serverId={serverId}
          containerId={logsTarget.container_id}
          containerName={logsTarget.container_name}
        />
      )}

      <Dialog open={!!confirm} onClose={() => setConfirm(null)}>
        <DialogTitle>{confirm ? ACTION_LABEL[confirm.action] : ''} контейнер?</DialogTitle>
        <DialogContent>
          <Typography>
            {ACTION_LABEL[confirm?.action ?? 'start']} контейнер <strong>{confirm?.containerName}</strong>?
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirm(null)}>Отмена</Button>
          <Button
            variant="contained"
            color={confirm?.action === 'delete' ? 'error' : 'primary'}
            onClick={handleConfirm}
            disabled={isPending}
            startIcon={isPending ? <CircularProgress size={14} /> : null}
          >
            {confirm ? ACTION_LABEL[confirm.action] : ''}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
