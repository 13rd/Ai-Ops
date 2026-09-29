import {
  Circle as CircleIcon,
  OpenInNew as OpenInNewIcon,
  Terminal as TerminalIcon,
} from '@mui/icons-material';
import {
  Box,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import type { Server, ServerStatus } from '@/entities/Server';
import { fromNow } from '@/shared/utils/formatters';

interface StatusConfig {
  color: 'success' | 'warning' | 'error';
  label: string;
}

const STATUS_CONFIG: Record<ServerStatus, StatusConfig> = {
  online: { color: 'success', label: 'Онлайн' },
  offline: { color: 'error', label: 'Офлайн' },
  degraded: { color: 'warning', label: 'Деградация' },
};

const ENV_COLOR: Record<string, 'default' | 'primary' | 'secondary' | 'warning' | 'error'> = {
  prod: 'error',
  production: 'error',
  staging: 'warning',
  dev: 'default',
  development: 'default',
};

interface ServerCardProps {
  server: Server;
}

export function ServerCard({ server }: ServerCardProps) {
  const navigate = useNavigate();
  const status = STATUS_CONFIG[server.status as ServerStatus] ?? { color: 'error', label: server.status };

  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardActionArea onClick={() => navigate(`/servers/${server.id}`)} sx={{ height: '100%' }}>
        <CardContent>
          <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }} noWrap>
              {server.name}
            </Typography>
            <Tooltip title={status.label}>
              <CircleIcon color={status.color} sx={{ fontSize: 14, mt: 0.4 }} />
            </Tooltip>
          </Stack>

          <Typography variant="body2" color="text.secondary" noWrap sx={{ mb: 1.5 }}>
            {server.host}:{server.port}
          </Typography>

          <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap', mb: 1.5 }}>
            {server.environment && (
              <Chip
                label={server.environment}
                size="small"
                color={ENV_COLOR[server.environment.toLowerCase()] ?? 'default'}
                variant="outlined"
              />
            )}
            {server.tags.slice(0, 3).map((tag) => (
              <Chip key={tag} label={tag} size="small" variant="outlined" />
            ))}
            {server.tags.length > 3 && (
              <Chip label={`+${server.tags.length - 3}`} size="small" variant="outlined" />
            )}
          </Stack>

          <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="caption" color="text.secondary">
              {server.last_seen ? `Был ${fromNow(server.last_seen)}` : 'Ещё не подключался'}
            </Typography>
            <Box>
              <Tooltip title="Открыть детали">
                <OpenInNewIcon sx={{ fontSize: 16, color: 'text.secondary', mr: 0.5 }} />
              </Tooltip>
              <Tooltip title="Открыть консоль">
                <TerminalIcon
                  sx={{ fontSize: 16, color: 'text.secondary', cursor: 'pointer' }}
                  onClick={(e) => {
                    e.stopPropagation();
                    navigate(`/servers/${server.id}/console`);
                  }}
                />
              </Tooltip>
            </Box>
          </Stack>
        </CardContent>
      </CardActionArea>
    </Card>
  );
}
