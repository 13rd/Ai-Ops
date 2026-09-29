import { zodResolver } from '@hookform/resolvers/zod';
import {
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  MenuItem,
  TextField,
  Typography,
} from '@mui/material';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import type { Server } from '@/entities/Server';
import { useCreateServer, useUpdateServer } from '@/features/servers/hooks';

const serverSchema = z.object({
  name: z.string().min(1, 'Обязательное поле'),
  host: z.string().min(1, 'Обязательное поле'),
  port: z.number().int().min(1).max(65535),
  connection_type: z.string().min(1),
  environment: z.string().optional(),
  tags: z.string().optional(),
  ssh_username: z.string().optional(),
  ssh_password: z.string().optional(),
  ssh_private_key: z.string().optional(),
});

type FormData = z.infer<typeof serverSchema>;

interface Props {
  open: boolean;
  onClose: () => void;
  server?: Server;
  onSuccess?: (server: Server) => void;
}

export function ServerFormDialog({ open, onClose, server, onSuccess }: Props) {
  const isEdit = !!server;
  const create = useCreateServer();
  const update = useUpdateServer(server?.id ?? 0);
  const isPending = create.isPending || update.isPending;

  const { register, handleSubmit, reset, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(serverSchema),
    defaultValues: {
      name: '', host: '', port: 22, connection_type: 'ssh',
      environment: '', tags: '', ssh_username: '', ssh_password: '', ssh_private_key: '',
    },
  });

  useEffect(() => {
    if (server) {
      reset({
        name: server.name,
        host: server.host,
        port: server.port,
        connection_type: server.connection_type,
        environment: server.environment ?? '',
        tags: server.tags.join(', '),
        ssh_username: '',
        ssh_password: '',
        ssh_private_key: '',
      });
    } else {
      reset({ name: '', host: '', port: 22, connection_type: 'ssh', environment: '', tags: '', ssh_username: '', ssh_password: '', ssh_private_key: '' });
    }
  }, [server, reset]);

  async function onSubmit(data: FormData) {
    const tags = data.tags ? data.tags.split(',').map((t) => t.trim()).filter(Boolean) : [];
    const payload = {
      name: data.name,
      host: data.host,
      port: data.port,
      connection_type: data.connection_type,
      environment: data.environment || undefined,
      tags,
      ...(data.ssh_username ? { ssh_username: data.ssh_username } : {}),
      ...(data.ssh_password ? { ssh_password: data.ssh_password } : {}),
      ...(data.ssh_private_key ? { ssh_private_key: data.ssh_private_key } : {}),
    };
    const result = isEdit ? await update.mutateAsync(payload) : await create.mutateAsync(payload);
    onSuccess?.(result);
    onClose();
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{isEdit ? 'Редактировать сервер' : 'Добавить сервер'}</DialogTitle>

      <Box component="form" onSubmit={handleSubmit(onSubmit)} noValidate>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <Grid container spacing={2}>
            <Grid size={8}>
              <TextField
                label="Название"
                fullWidth
                error={!!errors.name}
                helperText={errors.name?.message}
                {...register('name')}
              />
            </Grid>
            <Grid size={4}>
              <TextField label="Окружение" fullWidth select defaultValue="" {...register('environment')}>
                <MenuItem value="">— Нет —</MenuItem>
                <MenuItem value="dev">dev</MenuItem>
                <MenuItem value="staging">staging</MenuItem>
                <MenuItem value="prod">prod</MenuItem>
              </TextField>
            </Grid>
            <Grid size={8}>
              <TextField
                label="Хост / IP"
                fullWidth
                error={!!errors.host}
                helperText={errors.host?.message}
                {...register('host')}
              />
            </Grid>
            <Grid size={4}>
              <TextField
                label="Порт"
                type="number"
                fullWidth
                error={!!errors.port}
                helperText={errors.port?.message}
                {...register('port', { valueAsNumber: true })}
              />
            </Grid>
            <Grid size={12}>
              <TextField
                label="Теги (через запятую)"
                fullWidth
                placeholder="web, linux, nginx"
                {...register('tags')}
              />
            </Grid>
          </Grid>

          <Divider />
          <Typography variant="caption" color="text.secondary">
            SSH-учётные данные{isEdit && ' — оставьте пустыми, чтобы не менять'}
          </Typography>

          <Grid container spacing={2}>
            <Grid size={12}>
              <TextField label="SSH-пользователь" fullWidth autoComplete="off" {...register('ssh_username')} />
            </Grid>
            <Grid size={12}>
              <TextField label="SSH-пароль" type="password" fullWidth autoComplete="new-password" {...register('ssh_password')} />
            </Grid>
            <Grid size={12}>
              <TextField
                label="SSH-приватный ключ"
                multiline
                rows={4}
                fullWidth
                placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
                {...register('ssh_private_key')}
              />
            </Grid>
          </Grid>
        </DialogContent>

        <DialogActions>
          <Button onClick={onClose} disabled={isPending}>Отмена</Button>
          <Button
            type="submit"
            variant="contained"
            disabled={isPending}
            startIcon={isPending ? <CircularProgress size={16} color="inherit" /> : null}
          >
            {isEdit ? 'Сохранить' : 'Создать'}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
}
