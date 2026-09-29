import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { SnackbarProvider } from 'notistack';
import App from './App';
import { AuthProvider } from '@/features/auth/AuthContext';
import { QueryProvider } from '@/app/QueryProvider';
import { ColorModeProvider } from '@/shared/theme/ColorModeProvider';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ColorModeProvider>
      <SnackbarProvider maxSnack={4} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}>
        <QueryProvider>
          <AuthProvider>
            <App />
          </AuthProvider>
        </QueryProvider>
      </SnackbarProvider>
    </ColorModeProvider>
  </StrictMode>,
);
