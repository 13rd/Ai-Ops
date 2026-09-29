import { zodResolver } from '@hookform/resolvers/zod';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Container,
  Paper,
  TextField,
  Typography,
} from '@mui/material';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useLocation, useNavigate } from 'react-router-dom';
import { z } from 'zod';
import { useAuth } from '@/features/auth/AuthContext';
import { ApiError } from '@/shared/api/types';

const loginSchema = z.object({
  username: z.string().min(1, 'Введите имя пользователя'),
  password: z.string().min(8, 'Пароль должен содержать не менее 8 символов'),
});

type LoginFormData = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? '/';

  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({ resolver: zodResolver(loginSchema) });

  async function onSubmit(data: LoginFormData) {
    setServerError(null);
    try {
      await login(data.username, data.password);
      navigate(from, { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === 'authentication_failed') {
          setServerError('Неверное имя пользователя или пароль.');
        } else if (err.code === 'permission_denied') {
          setServerError('Ваш аккаунт неактивен. Обратитесь к администратору.');
        } else {
          setServerError(err.message);
        }
      } else {
        setServerError('Ошибка сети. Попробуйте ещё раз.');
      }
    }
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: 'background.default',
      }}
    >
      <Container maxWidth="xs">
        <Paper elevation={4} sx={{ p: 4, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box sx={{ textAlign: 'center', mb: 1 }}>
            <Typography variant="h5" sx={{ fontWeight: 'bold', color: 'primary.main' }}>
              Server Monitor
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Войдите для продолжения
            </Typography>
          </Box>

          {serverError && (
            <Alert severity="error" onClose={() => setServerError(null)}>
              {serverError}
            </Alert>
          )}

          <Box
            component="form"
            onSubmit={handleSubmit(onSubmit)}
            noValidate
            sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
          >
            <TextField
              label="Имя пользователя"
              autoComplete="username"
              autoFocus
              fullWidth
              error={!!errors.username}
              helperText={errors.username?.message}
              disabled={isSubmitting}
              {...register('username')}
            />

            <TextField
              label="Пароль"
              type="password"
              autoComplete="current-password"
              fullWidth
              error={!!errors.password}
              helperText={errors.password?.message}
              disabled={isSubmitting}
              {...register('password')}
            />

            <Button
              type="submit"
              variant="contained"
              size="large"
              fullWidth
              disabled={isSubmitting}
              startIcon={isSubmitting ? <CircularProgress size={18} color="inherit" /> : null}
            >
              {isSubmitting ? 'Вход…' : 'Войти'}
            </Button>
          </Box>
        </Paper>
      </Container>
    </Box>
  );
}
