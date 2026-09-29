import { Box, Button, Typography } from '@mui/material';
import { useNavigate } from 'react-router-dom';

export default function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <Box sx={{ textAlign: 'center', py: 12 }}>
      <Typography variant="h3" sx={{ fontWeight: 700, mb: 1 }}>404</Typography>
      <Typography variant="h6" color="text.secondary" sx={{ mb: 3 }}>Страница не найдена</Typography>
      <Button variant="contained" onClick={() => navigate('/')}>На главную</Button>
    </Box>
  );
}
