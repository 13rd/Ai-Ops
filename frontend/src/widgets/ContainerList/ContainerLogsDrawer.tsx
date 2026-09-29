import { Close as CloseIcon, Refresh as RefreshIcon } from '@mui/icons-material';
import {
  Box,
  CircularProgress,
  Drawer,
  FormControlLabel,
  IconButton,
  MenuItem,
  Select,
  Stack,
  Switch,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material';
import { useEffect, useRef, useState } from 'react';
import { useContainerLogs, useContainerLogStream } from '@/features/containers/hooks';

const TAIL_OPTIONS = [50, 100, 200, 500];

interface Props {
  open: boolean;
  onClose: () => void;
  serverId: number;
  containerId: string;
  containerName: string;
}

export function ContainerLogsDrawer({ open, onClose, serverId, containerId, containerName }: Props) {
  const [tail, setTail] = useState(100);
  const [follow, setFollow] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const { data, isFetching, refetch } = useContainerLogs(serverId, open ? containerId : null, tail);
  const stream = useContainerLogStream(serverId, containerId, tail, follow && open);

  const displayLines = follow ? stream.lines : (data?.lines ?? []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [displayLines.length]);

  useEffect(() => {
    if (!open) setFollow(false);
  }, [open]);

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      slotProps={{
        paper: { sx: { width: { xs: '100%', sm: 600 }, display: 'flex', flexDirection: 'column' } },
      }}
    >
      <Toolbar sx={{ borderBottom: 1, borderColor: 'divider', gap: 1, flexShrink: 0 }}>
        <Typography
          variant="subtitle1"
          sx={{ flex: 1, fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
        >
          Логи: {containerName}
        </Typography>
        <Tooltip title="Закрыть">
          <IconButton edge="end" onClick={onClose}><CloseIcon /></IconButton>
        </Tooltip>
      </Toolbar>

      <Stack
        direction="row"
        spacing={2}
        sx={{ alignItems: 'center', px: 2, py: 1, borderBottom: 1, borderColor: 'divider', flexShrink: 0 }}
      >
        <Select
          size="small"
          value={tail}
          onChange={(e) => setTail(Number(e.target.value))}
          disabled={follow}
          sx={{ minWidth: 100 }}
        >
          {TAIL_OPTIONS.map((n) => (
            <MenuItem key={n} value={n}>{n} строк</MenuItem>
          ))}
        </Select>

        <FormControlLabel
          control={<Switch checked={follow} onChange={(e) => setFollow(e.target.checked)} size="small" />}
          label="Следить"
        />

        {!follow && (
          <Tooltip title="Обновить">
            <span>
              <IconButton size="small" onClick={() => void refetch()} disabled={isFetching}>
                {isFetching ? <CircularProgress size={16} /> : <RefreshIcon fontSize="small" />}
              </IconButton>
            </span>
          </Tooltip>
        )}

        {follow && (
          <Typography variant="caption" color={stream.connected ? 'success.main' : 'text.secondary'}>
            {stream.connected ? 'подключено' : 'соединение…'}
          </Typography>
        )}
      </Stack>

      <Box
        sx={{
          flex: 1,
          overflow: 'auto',
          bgcolor: '#0d1117',
          p: 1.5,
          fontFamily: 'monospace',
          fontSize: '0.75rem',
          color: '#c9d1d9',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-all',
        }}
      >
        {displayLines.length === 0 && !isFetching && (
          <Typography variant="caption" sx={{ color: '#8b949e' }}>Логи пусты</Typography>
        )}
        {isFetching && !follow && (
          <Box sx={{ display: 'flex', justifyContent: 'center', pt: 2 }}>
            <CircularProgress size={20} sx={{ color: '#8b949e' }} />
          </Box>
        )}
        {displayLines.map((line, i) => (
          <div key={i}>{line}</div>
        ))}
        <div ref={bottomRef} />
      </Box>
    </Drawer>
  );
}
