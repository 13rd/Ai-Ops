import {
  PersonAdd as AddIcon,
  Block as DeactivateIcon,
  Edit as EditIcon,
  People as PeopleIcon,
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
  IconButton,
  Pagination,
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
import type { AppUser } from '@/entities/User';
import { useDeactivateUser, useUsers } from '@/features/users/hooks';
import { ApiError } from '@/shared/api/types';
import { formatDate, fromNow } from '@/shared/utils/formatters';
import { UserFormDialog } from '@/widgets/UserFormDialog';

const PAGE_SIZE = 20;

const ROLE_LABEL: Record<string, string> = {
  admin: 'Администратор',
  operator: 'Оператор',
};

export default function UsersPage() {
  const { enqueueSnackbar } = useSnackbar();
  const [page, setPage] = useState(1);
  const [formOpen, setFormOpen] = useState(false);
  const [editUser, setEditUser] = useState<AppUser | undefined>(undefined);
  const [deactivateTarget, setDeactivateTarget] = useState<AppUser | null>(null);

  const { data, isLoading, isError } = useUsers(PAGE_SIZE, (page - 1) * PAGE_SIZE);
  const deactivate = useDeactivateUser();

  const users = data?.items ?? [];
  const total = data?.pagination?.total ?? 0;
  const pageCount = Math.ceil(total / PAGE_SIZE);

  function openCreate() { setEditUser(undefined); setFormOpen(true); }
  function openEdit(user: AppUser) { setEditUser(user); setFormOpen(true); }

  async function handleDeactivate() {
    if (!deactivateTarget) return;
    try {
      await deactivate.mutateAsync(deactivateTarget.id);
      enqueueSnackbar(`Пользователь «${deactivateTarget.username}» деактивирован`, { variant: 'success' });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Не удалось деактивировать';
      enqueueSnackbar(msg, { variant: 'error' });
    } finally {
      setDeactivateTarget(null);
    }
  }

  return (
    <Box>
      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
          <PeopleIcon />
          <Typography variant="h5">Пользователи</Typography>
          {total > 0 && <Chip label={total} size="small" />}
        </Stack>
        <Button startIcon={<AddIcon />} variant="contained" onClick={openCreate}>
          Новый пользователь
        </Button>
      </Stack>

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      ) : isError ? (
        <Alert severity="error">Не удалось загрузить пользователей.</Alert>
      ) : (
        <>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Имя пользователя</TableCell>
                  <TableCell>Email</TableCell>
                  <TableCell>Роль</TableCell>
                  <TableCell>Статус</TableCell>
                  <TableCell>Создан</TableCell>
                  <TableCell align="right">Действия</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {users.map((u) => (
                  <TableRow key={u.id} hover sx={{ opacity: u.is_active ? 1 : 0.5 }}>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontWeight: 500 }}>{u.username}</Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">{u.email}</Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={ROLE_LABEL[u.role] ?? u.role}
                        size="small"
                        color={u.role === 'admin' ? 'primary' : 'default'}
                      />
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={u.is_active ? 'Активен' : 'Неактивен'}
                        size="small"
                        color={u.is_active ? 'success' : 'default'}
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      <Tooltip title={formatDate(u.created_at)}>
                        <Typography variant="caption" color="text.secondary">
                          {fromNow(u.created_at)}
                        </Typography>
                      </Tooltip>
                    </TableCell>
                    <TableCell align="right">
                      <Stack direction="row" spacing={0.5} sx={{ justifyContent: 'flex-end' }}>
                        <Tooltip title="Редактировать">
                          <IconButton size="small" onClick={() => openEdit(u)}>
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        {u.is_active && (
                          <Tooltip title="Деактивировать">
                            <IconButton size="small" color="warning" onClick={() => setDeactivateTarget(u)}>
                              <DeactivateIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        )}
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {pageCount > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
              <Pagination count={pageCount} page={page} onChange={(_, p) => setPage(p)} color="primary" size="small" />
            </Box>
          )}
        </>
      )}

      <UserFormDialog open={formOpen} onClose={() => setFormOpen(false)} user={editUser} />

      <Dialog open={Boolean(deactivateTarget)} onClose={() => setDeactivateTarget(null)}>
        <DialogTitle>Деактивировать пользователя?</DialogTitle>
        <DialogContent>
          <Typography>
            Деактивировать <strong>{deactivateTarget?.username}</strong>? Пользователь потеряет доступ к системе.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeactivateTarget(null)}>Отмена</Button>
          <Button
            color="warning"
            variant="contained"
            onClick={handleDeactivate}
            disabled={deactivate.isPending}
            startIcon={deactivate.isPending ? <CircularProgress size={14} /> : null}
          >
            Деактивировать
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
