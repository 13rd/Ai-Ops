import {
  Box,
  Button,
  Checkbox,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  FormHelperText,
  InputLabel,
  MenuItem,
  Radio,
  RadioGroup,
  Select,
  Stack,
  Switch,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';
import { useSnackbar } from 'notistack';
import { useEffect, useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import type { AppUser } from '@/entities/User';
import {
  useCreateUser,
  useSetUserServers,
  useUpdateUser,
  useUserServers,
} from '@/features/users/hooks';
import { usersApi } from '@/features/users/api';
import { useServers } from '@/features/servers/hooks';
import { ApiError } from '@/shared/api/types';

const profileSchema = z.object({
  email: z.string().email('Некорректный email'),
  username: z.string().min(1, 'Обязательное поле'),
  role: z.enum(['admin', 'operator']),
  is_active: z.boolean(),
  password: z.string().optional(),
});

type ProfileForm = z.infer<typeof profileSchema>;

interface ServerAccessRow {
  server_id: number;
  permission: 'read' | 'write';
  checked: boolean;
}

interface Props {
  open: boolean;
  onClose: () => void;
  user?: AppUser;
}

export function UserFormDialog({ open, onClose, user }: Props) {
  const isEdit = Boolean(user);
  const { enqueueSnackbar } = useSnackbar();
  const [tab, setTab] = useState(0);

  const createUser = useCreateUser();
  const updateUser = useUpdateUser(user?.id ?? 0);
  const setServers = useSetUserServers(user?.id ?? 0);
  const { data: userServersData } = useUserServers(user?.id ?? 0);
  const { data: serversData } = useServers({ limit: 1000 });

  const allServers = serversData?.items ?? [];
  const [accessRows, setAccessRows] = useState<ServerAccessRow[]>([]);

  useEffect(() => {
    if (!open) return;
    const existing = userServersData ?? [];
    const rows: ServerAccessRow[] = allServers.map((s) => {
      const found = existing.find((e) => e.server_id === s.id);
      return { server_id: s.id, permission: (found?.permission as 'read' | 'write') ?? 'read', checked: Boolean(found) };
    });
    setAccessRows(rows);
  }, [open, userServersData, allServers]);

  const { register, control, handleSubmit, reset, formState: { errors } } = useForm<ProfileForm>({
    resolver: zodResolver(profileSchema),
    defaultValues: { email: user?.email ?? '', username: user?.username ?? '', role: user?.role ?? 'operator', is_active: user?.is_active ?? true, password: '' },
  });

  useEffect(() => {
    if (open) {
      reset({ email: user?.email ?? '', username: user?.username ?? '', role: user?.role ?? 'operator', is_active: user?.is_active ?? true, password: '' });
      setTab(0);
    }
  }, [open, user, reset]);

  const isPending = createUser.isPending || updateUser.isPending || setServers.isPending;

  async function onSubmit(data: ProfileForm) {
    try {
      let userId = user?.id;
      if (isEdit) {
        const payload: Record<string, unknown> = { email: data.email, username: data.username, role: data.role, is_active: data.is_active };
        if (data.password) payload.password = data.password;
        await updateUser.mutateAsync(payload);
      } else {
        if (!data.password) { enqueueSnackbar('Пароль обязателен', { variant: 'error' }); return; }
        const created = await createUser.mutateAsync({ email: data.email, username: data.username, role: data.role, password: data.password });
        userId = created.id;
      }
      if (userId) {
        const accesses = accessRows.filter((r) => r.checked).map((r) => ({ server_id: r.server_id, permission: r.permission }));
        await usersApi.setServers(userId, accesses);
      }
      enqueueSnackbar(isEdit ? 'Пользователь обновлён' : 'Пользователь создан', { variant: 'success' });
      onClose();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Ошибка операции';
      enqueueSnackbar(msg, { variant: 'error' });
    }
  }

  function toggleServer(serverId: number) {
    setAccessRows((prev) => prev.map((r) => (r.server_id === serverId ? { ...r, checked: !r.checked } : r)));
  }

  function setPermission(serverId: number, permission: 'read' | 'write') {
    setAccessRows((prev) => prev.map((r) => (r.server_id === serverId ? { ...r, permission, checked: true } : r)));
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{isEdit ? 'Редактировать пользователя' : 'Новый пользователь'}</DialogTitle>

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ px: 3, borderBottom: 1, borderColor: 'divider' }}>
        <Tab label="Профиль" />
        <Tab label="Доступ к серверам" />
      </Tabs>

      <DialogContent sx={{ pt: 2 }}>
        <Box hidden={tab !== 0}>
          <Stack spacing={2}>
            <TextField label="Имя пользователя" size="small" fullWidth error={Boolean(errors.username)} helperText={errors.username?.message} {...register('username')} />
            <TextField label="Email" size="small" fullWidth error={Boolean(errors.email)} helperText={errors.email?.message} {...register('email')} />
            <Controller
              name="role"
              control={control}
              render={({ field }) => (
                <FormControl size="small" fullWidth error={Boolean(errors.role)}>
                  <InputLabel>Роль</InputLabel>
                  <Select {...field} label="Роль">
                    <MenuItem value="operator">Оператор</MenuItem>
                    <MenuItem value="admin">Администратор</MenuItem>
                  </Select>
                  {errors.role && <FormHelperText>{errors.role.message}</FormHelperText>}
                </FormControl>
              )}
            />
            <TextField
              label={isEdit ? 'Новый пароль (оставьте пустым, чтобы не менять)' : 'Пароль'}
              type="password"
              size="small"
              fullWidth
              error={Boolean(errors.password)}
              helperText={errors.password?.message}
              {...register('password')}
            />
            {isEdit && (
              <Controller
                name="is_active"
                control={control}
                render={({ field }) => (
                  <FormControlLabel control={<Switch checked={field.value} onChange={field.onChange} />} label="Активен" />
                )}
              />
            )}
          </Stack>
        </Box>

        <Box hidden={tab !== 1}>
          {allServers.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>Серверов нет</Typography>
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell padding="checkbox" />
                    <TableCell>Сервер</TableCell>
                    <TableCell>Права</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {accessRows.map((row) => {
                    const server = allServers.find((s) => s.id === row.server_id);
                    return (
                      <TableRow key={row.server_id}>
                        <TableCell padding="checkbox">
                          <Checkbox checked={row.checked} onChange={() => toggleServer(row.server_id)} size="small" />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">{server?.name}</Typography>
                          <Typography variant="caption" color="text.secondary">{server?.host}</Typography>
                        </TableCell>
                        <TableCell>
                          <RadioGroup row value={row.permission} onChange={(e) => setPermission(row.server_id, e.target.value as 'read' | 'write')}>
                            <FormControlLabel value="read" control={<Radio size="small" disabled={!row.checked} />} label="Чтение" />
                            <FormControlLabel value="write" control={<Radio size="small" disabled={!row.checked} />} label="Запись" />
                          </RadioGroup>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Box>
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose} disabled={isPending}>Отмена</Button>
        <Button variant="contained" onClick={handleSubmit(onSubmit)} disabled={isPending} startIcon={isPending ? <CircularProgress size={14} /> : null}>
          {isEdit ? 'Сохранить' : 'Создать'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
