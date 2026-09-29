import {
  Alert,
  Box,
  Button,
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
import { useLLMSettings, useUpdateLLMSettings } from '@/features/llmSettings/hooks';
import { ApiError } from '@/shared/api/types';
import { formatDate } from '@/shared/utils/formatters';

const PLACEHOLDER_HINT =
  '{anomaly_type}, {severity}, {server_name}, {environment}, ' +
  '{metrics_summary}, {top_features}, {history_summary}';

export default function LLMSettingsPage() {
  const { enqueueSnackbar } = useSnackbar();
  const { data: settings, isLoading } = useLLMSettings();
  const update = useUpdateLLMSettings();

  const [enabled, setEnabled] = useState(true);
  const [model, setModel] = useState('');
  const [timeoutSec, setTimeoutSec] = useState('');
  const [keepAlive, setKeepAlive] = useState('');
  const [promptTemplate, setPromptTemplate] = useState('');

  useEffect(() => {
    if (!settings) return;
    setEnabled(settings.enabled);
    setModel(settings.model ?? '');
    setTimeoutSec(settings.timeout_sec != null ? String(settings.timeout_sec) : '');
    setKeepAlive(settings.keep_alive ?? '');
    setPromptTemplate(settings.prompt_template ?? '');
  }, [settings]);

  async function handleSave() {
    const trimmedTimeout = timeoutSec.trim();
    if (trimmedTimeout && (!/^\d+$/.test(trimmedTimeout) || Number(trimmedTimeout) <= 0)) {
      enqueueSnackbar('Таймаут должен быть положительным целым числом секунд', { variant: 'warning' });
      return;
    }
    try {
      await update.mutateAsync({
        enabled,
        model: model.trim() || null,
        timeout_sec: trimmedTimeout ? Number(trimmedTimeout) : null,
        keep_alive: keepAlive.trim() || null,
        prompt_template: promptTemplate.trim() || null,
      });
      enqueueSnackbar('Настройки LLM-рекомендатора сохранены', { variant: 'success' });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Не удалось сохранить настройки';
      enqueueSnackbar(msg, { variant: 'error' });
    }
  }

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ maxWidth: 760 }}>
      <Typography variant="h5" sx={{ mb: 0.5 }}>Настройки LLM-рекомендатора</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Управление поведением ИИ-генератора рекомендаций (Ollama) — глобально для всех серверов.
        Пустые поля означают использование значений по умолчанию из конфигурации сервера.
      </Typography>

      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Stack spacing={2.5} divider={<Divider />}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <Box>
              <Typography variant="body2" sx={{ fontWeight: 500 }}>LLM-рекомендации включены</Typography>
              <Typography variant="caption" color="text.secondary">
                Если выключено — рекомендации формируются только по шаблонам, без обращения к Ollama
              </Typography>
            </Box>
            <FormControlLabel
              control={<Switch checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />}
              label=""
            />
          </Stack>

          <Stack spacing={2}>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>Параметры подключения к Ollama</Typography>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <TextField
                label="Модель"
                size="small"
                fullWidth
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="например, qwen2.5:3b"
              />
              <TextField
                label="Таймаут (сек.)"
                size="small"
                fullWidth
                value={timeoutSec}
                onChange={(e) => setTimeoutSec(e.target.value)}
                placeholder="например, 60"
              />
              <TextField
                label="Keep-alive"
                size="small"
                fullWidth
                value={keepAlive}
                onChange={(e) => setKeepAlive(e.target.value)}
                placeholder="например, 30m"
              />
            </Stack>
          </Stack>

          <Stack spacing={1.5}>
            <Box>
              <Typography variant="body2" sx={{ fontWeight: 500 }}>Шаблон промпта</Typography>
              <Typography variant="caption" color="text.secondary">
                Должен содержать блоки <code>EXPLANATION:</code> и <code>COMMAND:</code> и
                использовать только следующие плейсхолдеры: {PLACEHOLDER_HINT}
              </Typography>
            </Box>
            <TextField
              size="small"
              fullWidth
              multiline
              minRows={8}
              maxRows={20}
              value={promptTemplate}
              onChange={(e) => setPromptTemplate(e.target.value)}
              placeholder="Оставьте пустым, чтобы использовать шаблон по умолчанию"
              sx={{ fontFamily: 'monospace', '& textarea': { fontFamily: 'monospace', fontSize: '0.8rem' } }}
            />
            <Alert severity="info" variant="outlined">
              При ошибке в шаблоне (неизвестный плейсхолдер, опечатка в фигурных скобках) система
              автоматически использует шаблон по умолчанию для этого запроса.
            </Alert>
          </Stack>

          <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
            <Button
              variant="contained"
              onClick={handleSave}
              disabled={update.isPending}
              startIcon={update.isPending ? <CircularProgress size={14} /> : null}
            >
              Сохранить
            </Button>
            {settings?.updated_at && (
              <Typography variant="caption" color="text.secondary">
                Обновлено: {formatDate(settings.updated_at)}
              </Typography>
            )}
          </Stack>
        </Stack>
      </Paper>
    </Box>
  );
}
