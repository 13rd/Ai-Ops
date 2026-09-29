import { Add as AddIcon, FilterList as FilterListIcon } from '@mui/icons-material';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Grid,
  MenuItem,
  Pagination,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useState } from 'react';
import { useAuth } from '@/features/auth/AuthContext';
import { useServers } from '@/features/servers/hooks';
import { ServerCard } from '@/widgets/ServerCard';
import { ServerFormDialog } from '@/widgets/ServerFormDialog';

const PAGE_SIZE = 12;

const ENVIRONMENTS = ['dev', 'staging', 'prod'];
const STATUSES = [
  { value: 'online', label: 'Онлайн' },
  { value: 'offline', label: 'Офлайн' },
  { value: 'degraded', label: 'Деградация' },
];
const SORT_OPTIONS = [
  { value: 'created_at', label: 'Дата добавления' },
  { value: 'name', label: 'Название' },
  { value: 'last_seen', label: 'Последний визит' },
];

export default function ServersPage() {
  const { isAdmin } = useAuth();
  const [page, setPage] = useState(1);
  const [environment, setEnvironment] = useState('');
  const [status, setStatus] = useState('');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [showFilters, setShowFilters] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);

  const { data: serversData, isLoading, isError } = useServers({
    skip: (page - 1) * PAGE_SIZE,
    limit: PAGE_SIZE,
    environment: environment || undefined,
    status: status || undefined,
    sort_by: sortBy,
    sort_order: sortOrder,
  });

  const servers = serversData?.items ?? [];
  const totalPages = Math.ceil((serversData?.pagination?.total ?? 0) / PAGE_SIZE);
  const hasFilters = !!environment || !!status;

  function clearFilters() {
    setEnvironment('');
    setStatus('');
    setPage(1);
  }

  return (
    <Box>
      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5">Серверы</Typography>
        <Stack direction="row" spacing={1}>
          <Button
            startIcon={<FilterListIcon />}
            variant={showFilters ? 'contained' : 'outlined'}
            onClick={() => setShowFilters((v) => !v)}
          >
            Фильтры
            {hasFilters && (
              <Chip
                label={[environment, status].filter(Boolean).length}
                size="small"
                color="primary"
                sx={{ ml: 0.5, height: 16, fontSize: 10 }}
              />
            )}
          </Button>
          {isAdmin && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
              Новый сервер
            </Button>
          )}
        </Stack>
      </Stack>

      <Collapse in={showFilters}>
        <Stack direction="row" spacing={2} sx={{ mb: 2, flexWrap: 'wrap' }}>
          <TextField
            select
            label="Окружение"
            value={environment}
            onChange={(e) => { setEnvironment(e.target.value); setPage(1); }}
            sx={{ minWidth: 140 }}
          >
            <MenuItem value="">Все</MenuItem>
            {ENVIRONMENTS.map((e) => <MenuItem key={e} value={e}>{e}</MenuItem>)}
          </TextField>

          <TextField
            select
            label="Статус"
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1); }}
            sx={{ minWidth: 140 }}
          >
            <MenuItem value="">Все</MenuItem>
            {STATUSES.map((s) => <MenuItem key={s.value} value={s.value}>{s.label}</MenuItem>)}
          </TextField>

          <TextField
            select
            label="Сортировка"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            sx={{ minWidth: 160 }}
          >
            {SORT_OPTIONS.map((o) => <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>)}
          </TextField>

          <TextField
            select
            label="Порядок"
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value as 'asc' | 'desc')}
            sx={{ minWidth: 140 }}
          >
            <MenuItem value="desc">Сначала новые</MenuItem>
            <MenuItem value="asc">Сначала старые</MenuItem>
          </TextField>

          {hasFilters && (
            <Button variant="text" onClick={clearFilters} sx={{ alignSelf: 'center' }}>
              Сбросить
            </Button>
          )}
        </Stack>
      </Collapse>

      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
          <CircularProgress />
        </Box>
      )}

      {isError && (
        <Typography color="error" sx={{ py: 4, textAlign: 'center' }}>
          Не удалось загрузить серверы.
        </Typography>
      )}

      {!isLoading && !isError && servers.length === 0 && (
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <Typography variant="h6" color="text.secondary" gutterBottom>
            Серверов пока нет
          </Typography>
          {isAdmin && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
              Добавить первый сервер
            </Button>
          )}
        </Box>
      )}

      {servers.length > 0 && (
        <Grid container spacing={2}>
          {servers.map((server) => (
            <Grid key={server.id} size={{ xs: 12, sm: 6, md: 4, lg: 3 }}>
              <ServerCard server={server} />
            </Grid>
          ))}
        </Grid>
      )}

      {totalPages > 1 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
          <Pagination count={totalPages} page={page} onChange={(_, p) => setPage(p)} color="primary" />
        </Box>
      )}

      <ServerFormDialog open={createOpen} onClose={() => setCreateOpen(false)} />
    </Box>
  );
}
