import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  FormControlLabel,
  Paper,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import { useSnackbar } from 'notistack';
import { useEffect, useState } from 'react';
import { useAuth } from '@/features/auth/AuthContext';
import {
  useDeleteChannel,
  useNotificationChannels,
  useUpsertChannel,
} from '@/features/notifications/hooks';
import { ApiError } from '@/shared/api/types';
import { formatDate } from '@/shared/utils/formatters';

const ROLE_LABEL: Record<string, string> = { admin: 'Администратор', operator: 'Оператор' };

export default function ProfilePage() {
  const { user } = useAuth();
  const { enqueueSnackbar } = useSnackbar();
  const { data: channels = [], isLoading: channelsLoading } = useNotificationChannels();
  const upsert = useUpsertChannel();
  const deleteChannel = useDeleteChannel();

  const inapp = channels.find((c) => c.channel_type === 'inapp');
  const telegram = channels.find((c) => c.channel_type === 'telegram');

  const [inappEnabled, setInappEnabled] = useState<boolean>(inapp?.enabled ?? true);
  useEffect(() => { if (inapp) setInappEnabled(inapp.enabled); }, [inapp]);

  const [tgChatId, setTgChatId] = useState<string>('');
  const [tgEnabled, setTgEnabled] = useState<boolean>(true);
  useEffect(() => {
    if (telegram) { setTgChatId(String(telegram.config?.chat_id ?? '')); setTgEnabled(telegram.enabled); }
  }, [telegram]);

  async function handleInappToggle(enabled: boolean) {
    setInappEnabled(enabled);
    try {
      await upsert.mutateAsync({ channel_type: 'inapp', config: {}, enabled });
      enqueueSnackbar('Настройки уведомлений обновлены', { variant: 'success' });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Не удалось обновить';
      enqueueSnackbar(msg, { variant: 'error' });
      setInappEnabled(!enabled);
    }
  }

  async function handleTelegramSave() {
    if (!tgChatId.trim()) { enqueueSnackbar('Укажите Chat ID', { variant: 'warning' }); return; }
    try {
      await upsert.mutateAsync({ channel_type: 'telegram', config: { chat_id: tgChatId.trim() }, enabled: tgEnabled });
      enqueueSnackbar('Telegram-канал сохранён', { variant: 'success' });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Не удалось сохранить';
      enqueueSnackbar(msg, { variant: 'error' });
    }
  }

  async function handleTelegramDelete() {
    if (!telegram) return;
    try {
      await deleteChannel.mutateAsync(telegram.id);
      setTgChatId(''); setTgEnabled(true);
      enqueueSnackbar('Telegram-канал удалён', { variant: 'success' });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Не удалось удалить';
      enqueueSnackbar(msg, { variant: 'error' });
    }
  }

  return (
    <Box sx={{ maxWidth: 640 }}>
      <Typography variant="h5" sx={{ mb: 3 }}>Профиль</Typography>

      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1.5 }}>Учётная запись</Typography>
        <Stack spacing={1}>
          <Stack direction="row" spacing={2} sx={{ alignItems: 'center' }}>
            <Typography variant="body2" color="text.secondary" sx={{ minWidth: 100 }}>Имя пользователя</Typography>
            <Typography variant="body2">{user?.username}</Typography>
          </Stack>
          <Stack direction="row" spacing={2} sx={{ alignItems: 'center' }}>
            <Typography variant="body2" color="text.secondary" sx={{ minWidth: 100 }}>Email</Typography>
            <Typography variant="body2">{user?.email}</Typography>
          </Stack>
          <Stack direction="row" spacing={2} sx={{ alignItems: 'center' }}>
            <Typography variant="body2" color="text.secondary" sx={{ minWidth: 100 }}>Роль</Typography>
            <Chip label={ROLE_LABEL[user?.role ?? ''] ?? user?.role} size="small" color={user?.role === 'admin' ? 'primary' : 'default'} />
          </Stack>
          <Stack direction="row" spacing={2} sx={{ alignItems: 'center' }}>
            <Typography variant="body2" color="text.secondary" sx={{ minWidth: 100 }}>В системе с</Typography>
            <Typography variant="body2">{formatDate(user?.created_at ?? null)}</Typography>
          </Stack>
        </Stack>
      </Paper>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1.5 }}>Каналы уведомлений</Typography>

        {channelsLoading ? <CircularProgress size={24} /> : (
          <Stack spacing={2} divider={<Divider />}>
            <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 500 }}>В приложении</Typography>
                <Typography variant="caption" color="text.secondary">Уведомления в колокольчике</Typography>
              </Box>
              <FormControlLabel
                control={<Switch checked={inappEnabled} onChange={(e) => handleInappToggle(e.target.checked)} disabled={upsert.isPending} />}
                label=""
              />
            </Stack>

            <Box>
              <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
                <Box>
                  <Typography variant="body2" sx={{ fontWeight: 500 }}>Telegram</Typography>
                  <Typography variant="caption" color="text.secondary">Получать оповещения через Telegram-бота</Typography>
                </Box>
                {telegram && (
                  <FormControlLabel control={<Switch checked={tgEnabled} onChange={(e) => setTgEnabled(e.target.checked)} />} label="" />
                )}
              </Stack>

              <Stack spacing={1.5}>
                <TextField
                  label="Chat ID"
                  size="small"
                  value={tgChatId}
                  onChange={(e) => setTgChatId(e.target.value)}
                  placeholder="например, 123456789"
                  helperText={
                    <>
                      Узнайте свой Chat ID в боте{' '}
                      <Typography component="span" variant="inherit" sx={{ color: 'primary.main', cursor: 'pointer' }}
                        onClick={() => window.open('https://t.me/userinfobot', '_blank')}>
                        @userinfobot
                      </Typography>
                    </>
                  }
                />
                {!telegram && (
                  <FormControlLabel control={<Switch checked={tgEnabled} onChange={(e) => setTgEnabled(e.target.checked)} />} label="Включить" />
                )}
                <Stack direction="row" spacing={1}>
                  <Button variant="contained" size="small" onClick={handleTelegramSave} disabled={upsert.isPending} startIcon={upsert.isPending ? <CircularProgress size={14} /> : null}>
                    {telegram ? 'Обновить' : 'Подключить'}
                  </Button>
                  {telegram && (
                    <Button variant="outlined" color="error" size="small" onClick={handleTelegramDelete} disabled={deleteChannel.isPending}>
                      Удалить
                    </Button>
                  )}
                </Stack>
              </Stack>
            </Box>
          </Stack>
        )}
      </Paper>
    </Box>
  );
}
