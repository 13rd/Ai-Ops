import { lazy, Suspense } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { Box, CircularProgress } from '@mui/material';
import { AdminRoute, ProtectedRoute } from '@/features/auth/ProtectedRoute';
import { AppShell } from '@/widgets/AppShell';

const LoginPage = lazy(() => import('@/pages/LoginPage'));
const DashboardPage = lazy(() => import('@/pages/DashboardPage'));
const ServersPage = lazy(() => import('@/pages/ServersPage'));
const ServerDetailPage = lazy(() => import('@/pages/ServerDetailPage'));
const ConsolePage = lazy(() => import('@/pages/ConsolePage'));
const AnomaliesPage = lazy(() => import('@/pages/AnomaliesPage'));
const AnomalyDetailPage = lazy(() => import('@/pages/AnomalyDetailPage'));
const UsersPage = lazy(() => import('@/pages/UsersPage'));
const AuditLogPage = lazy(() => import('@/pages/AuditLogPage'));
const LLMSettingsPage = lazy(() => import('@/pages/LLMSettingsPage'));
const NotificationsPage = lazy(() => import('@/pages/NotificationsPage'));
const ProfilePage = lazy(() => import('@/pages/ProfilePage'));
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'));
const DemoControlPage = lazy(() => import('@/pages/DemoControlPage'));

function PageFallback() {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '200px' }}>
      <CircularProgress size={32} />
    </Box>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          <Route element={<ProtectedRoute />}>
            <Route element={<AppShell />}>
              {}
              <Route element={<AdminRoute />}>
                <Route path="/users" element={<UsersPage />} />
                <Route path="/audit-log" element={<AuditLogPage />} />
                <Route path="/llm-settings" element={<LLMSettingsPage />} />
              </Route>

              <Route path="/" element={<DashboardPage />} />
              <Route path="/servers" element={<ServersPage />} />
              <Route path="/servers/:id" element={<ServerDetailPage />} />
              <Route path="/servers/:id/console" element={<ConsolePage />} />
              <Route path="/anomalies" element={<AnomaliesPage />} />
              <Route path="/anomalies/:id" element={<AnomalyDetailPage />} />
              <Route path="/notifications" element={<NotificationsPage />} />
              <Route path="/profile" element={<ProfilePage />} />
              {import.meta.env.VITE_DEMO_MODE === 'true' && (
                <Route path="/demo" element={<DemoControlPage />} />
              )}
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
