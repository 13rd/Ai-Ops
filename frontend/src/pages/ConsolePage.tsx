import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowBack as ArrowBackIcon,
  LockOutlined as LockIcon,
  Refresh as RefreshIcon,
  Terminal as TerminalIcon,
} from '@mui/icons-material';
import { Alert, Box, Chip, CircularProgress, IconButton, Stack, Tooltip, Typography } from '@mui/material';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import '@xterm/xterm/css/xterm.css';
import { getAccessToken } from '@/shared/api/client';
import { useServer } from '@/features/servers/hooks';

type ConnState = 'connecting' | 'ready' | 'closed' | 'error';

const WS_BASE = (import.meta.env.VITE_WS_URL as string | undefined) ?? 'ws://localhost:8000/api/v1';

const CLOSE_REASONS: Record<number, string> = {
  4401: 'Ошибка аутентификации — войдите снова',
  4403: 'Доступ к серверу запрещён',
  4404: 'Сервер не найден',
  4500: 'Ошибка SSH-подключения — проверьте учётные данные',
};

const STATE_COLOR: Record<ConnState, 'default' | 'success' | 'warning' | 'error'> = {
  connecting: 'default',
  ready: 'success',
  closed: 'warning',
  error: 'error',
};

const STATE_LABEL: Record<ConnState, string> = {
  connecting: 'Подключение…',
  ready: 'Подключено',
  closed: 'Отключено',
  error: 'Ошибка',
};

export default function ConsolePage() {
  const { id } = useParams<{ id: string }>();
  const serverId = Number(id);
  const navigate = useNavigate();
  const { data: server } = useServer(serverId);

  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const [connState, setConnState] = useState<ConnState>('connecting');
  const [readOnly, setReadOnly] = useState(false);
  const [serverName, setServerName] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [reconnectKey, setReconnectKey] = useState(0);

  useEffect(() => {
    if (!containerRef.current) return;
    const term = new Terminal({
      cursorBlink: true,
      fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Courier New', monospace",
      fontSize: 14,
      lineHeight: 1.4,
      scrollback: 5000,
      theme: {
        background: '#0d1117', foreground: '#c9d1d9', cursor: '#58a6ff', cursorAccent: '#0d1117',
        selectionBackground: '#264f7880', black: '#484f58', brightBlack: '#6e7681',
        red: '#ff7b72', brightRed: '#ffa198', green: '#3fb950', brightGreen: '#56d364',
        yellow: '#d29922', brightYellow: '#e3b341', blue: '#58a6ff', brightBlue: '#79c0ff',
        magenta: '#bc8cff', brightMagenta: '#d2a8ff', cyan: '#39c5cf', brightCyan: '#56d4dd',
        white: '#b1bac4', brightWhite: '#f0f6fc',
      },
    });
    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();
    term.loadAddon(fitAddon);
    term.loadAddon(webLinksAddon);
    term.open(containerRef.current);
    requestAnimationFrame(() => fitAddon.fit());
    termRef.current = term;
    fitRef.current = fitAddon;
    return () => { term.dispose(); termRef.current = null; fitRef.current = null; };
  }, []);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) { setConnState('error'); setErrorMsg('Нет токена аутентификации — войдите снова'); return; }
    setConnState('connecting'); setErrorMsg('');
    const url = `${WS_BASE}/ws/servers/${serverId}/console?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;
    let disposed = false;
    const writeToTerm = (text: string) => { if (!disposed) termRef.current?.write(text); };
    const writelnToTerm = (text: string) => { if (!disposed) termRef.current?.writeln(text); };

    ws.onopen = () => { if (disposed) return; termRef.current?.clear(); writelnToTerm('\x1b[90m● Установка SSH-сессии…\x1b[0m'); };

    ws.onmessage = (ev: MessageEvent<string>) => {
      if (disposed) return;
      try {
        const msg = JSON.parse(ev.data) as { type: string; data?: unknown };
        switch (msg.type) {
          case 'ready': {
            const d = msg.data as { server_name: string; read_only: boolean };
            setServerName(d.server_name); setReadOnly(d.read_only); setConnState('ready'); termRef.current?.clear();
            if (d.read_only) writelnToTerm('\x1b[33m⚠  Режим только для чтения — ввод отключён\x1b[0m\r\n');
            break;
          }
          case 'output': writeToTerm(String(msg.data)); break;
          case 'error': writelnToTerm(`\r\n\x1b[31m✗ ${String(msg.data)}\x1b[0m`); break;
          case 'closed': if (!disposed) setConnState('closed'); writelnToTerm(`\r\n\x1b[90m● Сессия завершена: ${String(msg.data)}\x1b[0m`); break;
        }
      } catch { /* игнорируем некорректный JSON */ }
    };

    ws.onerror = () => { if (disposed) return; setConnState('error'); setErrorMsg('Ошибка WebSocket-подключения'); writelnToTerm('\r\n\x1b[31m✗ Ошибка соединения\x1b[0m'); };

    ws.onclose = (ev: CloseEvent) => {
      if (disposed) return;
      const reason = CLOSE_REASONS[ev.code];
      if (reason) { setConnState('error'); setErrorMsg(reason); writelnToTerm(`\r\n\x1b[31m✗ ${reason}\x1b[0m`); }
      else { setConnState((s) => (s === 'error' ? s : 'closed')); }
    };

    const dataDispose = termRef.current?.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'input', data }));
    });

    return () => { disposed = true; dataDispose?.dispose(); ws.close(); wsRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverId, reconnectKey]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const obs = new ResizeObserver(() => {
      if (!fitRef.current || !termRef.current) return;
      fitRef.current.fit();
      const { cols, rows } = termRef.current;
      if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: 'resize', cols, rows }));
    });
    obs.observe(container);
    return () => obs.disconnect();
  }, []);

  const handleReconnect = () => { termRef.current?.clear(); setReconnectKey((k) => k + 1); };
  const displayName = serverName || server?.name || `Сервер #${serverId}`;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', bgcolor: '#0d1117', borderRadius: 1, overflow: 'hidden', border: '1px solid', borderColor: 'divider' }}>
      <Stack direction="row" spacing={1.5} sx={{ px: 2, py: 1, bgcolor: '#161b22', borderBottom: '1px solid', borderColor: '#30363d', flexShrink: 0, alignItems: 'center' }}>
        <Tooltip title="Назад к серверу">
          <IconButton size="small" onClick={() => navigate(`/servers/${serverId}`)} sx={{ color: '#8b949e', '&:hover': { color: '#c9d1d9' } }}>
            <ArrowBackIcon fontSize="small" />
          </IconButton>
        </Tooltip>

        <TerminalIcon sx={{ color: '#3fb950', fontSize: 18 }} />

        <Typography variant="body2" sx={{ fontFamily: 'monospace', color: '#c9d1d9', fontWeight: 600 }}>
          {displayName}
        </Typography>

        <Chip size="small" label={STATE_LABEL[connState]} color={STATE_COLOR[connState]} variant="outlined" sx={{ height: 20, fontSize: '0.7rem' }} />

        {readOnly && connState === 'ready' && (
          <Chip size="small" icon={<LockIcon sx={{ fontSize: '0.8rem !important' }} />} label="Только чтение" color="warning" variant="outlined" sx={{ height: 20, fontSize: '0.7rem' }} />
        )}

        <Box sx={{ flex: 1 }} />

        {(connState === 'closed' || connState === 'error') && (
          <Tooltip title="Переподключиться">
            <IconButton size="small" onClick={handleReconnect} sx={{ color: '#58a6ff', '&:hover': { color: '#79c0ff' } }}>
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
      </Stack>

      {connState === 'error' && errorMsg && (
        <Alert
          severity="error"
          action={<IconButton color="inherit" size="small" onClick={handleReconnect}><RefreshIcon fontSize="small" /></IconButton>}
          sx={{ borderRadius: 0, flexShrink: 0, bgcolor: '#1f0a0a', color: '#ffa198', '& .MuiAlert-icon': { color: '#ff7b72' } }}
        >
          {errorMsg}
        </Alert>
      )}

      {connState === 'connecting' && (
        <Stack direction="row" spacing={1} sx={{ px: 2, py: 0.75, bgcolor: '#0d1117', borderBottom: '1px solid #21262d', flexShrink: 0, alignItems: 'center' }}>
          <CircularProgress size={12} thickness={5} sx={{ color: '#3fb950' }} />
          <Typography variant="caption" sx={{ color: '#8b949e', fontFamily: 'monospace' }}>
            Подключение к {displayName}…
          </Typography>
        </Stack>
      )}

      <Box ref={containerRef} sx={{ flex: 1, overflow: 'hidden', p: 0.5, '& .xterm': { height: '100%' }, '& .xterm-viewport': { borderRadius: 0 } }} />
    </Box>
  );
}
