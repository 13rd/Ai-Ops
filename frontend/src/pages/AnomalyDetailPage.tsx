import {
  ArrowBack as ArrowBackIcon,
  CheckCircle as ApproveIcon,
  Cancel as RejectIcon,
} from '@mui/icons-material';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Typography,
} from '@mui/material';
import { useSnackbar } from 'notistack';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { AnomalySeverity, AnomalyStatus } from '@/entities/Anomaly';
import type { RecommendationStatus } from '@/entities/Recommendation';
import { useAuth } from '@/features/auth/AuthContext';
import {
  useAnomaly,
  useAnomalyRecommendations,
  useApproveRecommendation,
  useRejectRecommendation,
  useUpdateAnomalyStatus,
} from '@/features/anomalies/hooks';
import { ApiError } from '@/shared/api/types';
import { formatDate, fromNow } from '@/shared/utils/formatters';

const SEVERITY_COLOR: Record<AnomalySeverity, 'default' | 'info' | 'warning' | 'error'> = {
  low: 'info',
  medium: 'warning',
  high: 'error',
  critical: 'error',
};

const STATUS_COLOR: Record<AnomalyStatus, 'error' | 'warning' | 'success' | 'default'> = {
  open: 'error',
  investigating: 'warning',
  resolved: 'success',
};

const REC_STATUS_COLOR: Record<RecommendationStatus, 'default' | 'warning' | 'success' | 'error' | 'info'> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'error',
  executed: 'info',
  failed: 'error',
};

function labelFor(type: string): string {
  return type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

interface ShapEntry {
  feature: string;
  value: number;
  abs: number;
}

type ShapPayload =
  | Record<string, number>
  | Array<{ metric: string; impact_percent: number }>;

function normalizeShap(data: ShapPayload | undefined | null): ShapEntry[] {
  if (!data) return [];
  if (Array.isArray(data)) {
    return data
      .map((item) => ({
        feature: String(item.metric),
        value: Number(item.impact_percent) / 100,
        abs: Math.abs(Number(item.impact_percent) / 100),
      }))
      .sort((a, b) => b.abs - a.abs)
      .slice(0, 12);
  }
  return Object.entries(data)
    .map(([feature, value]) => ({
      feature,
      value: Number(value),
      abs: Math.abs(Number(value)),
    }))
    .sort((a, b) => b.abs - a.abs)
    .slice(0, 12);
}

function ShapChart({ data }: { data: ShapPayload }) {
  const entries = normalizeShap(data);

  if (entries.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        No SHAP data available
      </Typography>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={Math.max(180, entries.length * 28)}>
      <BarChart data={entries} layout="vertical" margin={{ left: 16, right: 32, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" tickFormatter={(v: unknown) => Number(v).toFixed(3)} />
        <YAxis
          type="category"
          dataKey="feature"
          width={130}
          tick={{ fontSize: 12 }}
          tickFormatter={(v: unknown) => String(v).replace(/_/g, ' ')}
        />
        <Tooltip
          formatter={(value: unknown) => [Number(value).toFixed(4), 'SHAP']}
          labelFormatter={(label: unknown) => String(label).replace(/_/g, ' ')}
        />
        <Bar dataKey="value" name="SHAP value" radius={[0, 3, 3, 0]}>
          {entries.map((entry, index) => (
            <Cell
              key={index}
              fill={entry.value >= 0 ? '#f44336' : '#4caf50'}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export default function AnomalyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const anomalyId = parseInt(id ?? '0', 10);
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const { enqueueSnackbar } = useSnackbar();

  const { data: anomaly, isLoading, isError } = useAnomaly(anomalyId);
  const { data: recommendations = [] } = useAnomalyRecommendations(anomalyId);
  const updateStatus = useUpdateAnomalyStatus(anomalyId);
  const approve = useApproveRecommendation(anomalyId);
  const reject = useRejectRecommendation(anomalyId);

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (isError || !anomaly) {
    return (
      <Box sx={{ py: 4 }}>
        <Alert severity="error">Anomaly not found.</Alert>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/anomalies')} sx={{ mt: 2 }}>
          Back to Anomalies
        </Button>
      </Box>
    );
  }

  async function handleStatusChange(newStatus: string) {
    try {
      await updateStatus.mutateAsync(newStatus);
      enqueueSnackbar('Status updated', { variant: 'success' });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Failed to update status';
      enqueueSnackbar(msg, { variant: 'error' });
    }
  }

  async function handleApprove(recId: number) {
    try {
      await approve.mutateAsync(recId);
      enqueueSnackbar('Recommendation approved', { variant: 'success' });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Failed to approve';
      enqueueSnackbar(msg, { variant: 'error' });
    }
  }

  async function handleReject(recId: number) {
    try {
      await reject.mutateAsync(recId);
      enqueueSnackbar('Recommendation rejected', { variant: 'success' });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Failed to reject';
      enqueueSnackbar(msg, { variant: 'error' });
    }
  }

  const shapData = anomaly.shap_explanation ?? {};
  const metricsSnap = anomaly.metrics_snapshot ?? {};

  return (
    <Box>
      {/* Back */}
      <Button
        startIcon={<ArrowBackIcon />}
        size="small"
        onClick={() => navigate('/anomalies')}
        sx={{ mb: 1 }}
      >
        Anomalies
      </Button>

      {/* Header */}
      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'flex-start', mb: 2, flexWrap: 'wrap', gap: 1 }}>
        <Box>
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 0.5 }}>
            <Chip
              label={anomaly.severity}
              color={SEVERITY_COLOR[anomaly.severity] ?? 'default'}
              sx={{ textTransform: 'capitalize', fontWeight: 700 }}
            />
            <Typography variant="h6">{labelFor(anomaly.anomaly_type)}</Typography>
          </Stack>
          <Typography variant="body2" color="text.secondary">
            Server #{anomaly.server_id} · Detected {fromNow(anomaly.detected_at)} · {formatDate(anomaly.detected_at)}
          </Typography>
        </Box>

        {/* Status selector */}
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Status</InputLabel>
          <Select
            value={anomaly.status}
            label="Status"
            disabled={updateStatus.isPending}
            onChange={(e) => handleStatusChange(e.target.value)}
          >
            <MenuItem value="open">Open</MenuItem>
            <MenuItem value="investigating">Investigating</MenuItem>
            <MenuItem value="resolved">Resolved</MenuItem>
          </Select>
        </FormControl>
      </Stack>

      <Stack direction="row" spacing={1} sx={{ mb: 3 }}>
        <Chip
          label={anomaly.status}
          size="small"
          color={STATUS_COLOR[anomaly.status] ?? 'default'}
          variant="outlined"
          sx={{ textTransform: 'capitalize' }}
        />
        {anomaly.resolved_at && (
          <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center' }}>
            Resolved {fromNow(anomaly.resolved_at)}
          </Typography>
        )}
      </Stack>

      {/* Metrics & scores */}
      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
          Detection scores
        </Typography>
        <Stack direction="row" spacing={4} sx={{ flexWrap: 'wrap' }}>
          <Box>
            <Typography variant="caption" color="text.secondary">Reconstruction error</Typography>
            <Typography variant="body1" sx={{ fontFamily: 'monospace' }}>
              {anomaly.reconstruction_error.toFixed(6)}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Threshold</Typography>
            <Typography variant="body1" sx={{ fontFamily: 'monospace' }}>
              {anomaly.threshold.toFixed(6)}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Excess</Typography>
            <Typography
              variant="body1"
              sx={{ fontFamily: 'monospace', color: 'error.main', fontWeight: 600 }}
            >
              +{((anomaly.reconstruction_error - anomaly.threshold) / anomaly.threshold * 100).toFixed(1)}%
            </Typography>
          </Box>
        </Stack>
      </Paper>

      {/* Metrics snapshot */}
      {Object.keys(metricsSnap).length > 0 && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
            Metrics at detection time
          </Typography>
          <Stack direction="row" spacing={3} sx={{ flexWrap: 'wrap' }}>
            {Object.entries(metricsSnap).map(([key, val]) => (
              <Box key={key}>
                <Typography variant="caption" color="text.secondary">
                  {key.replace(/_/g, ' ')}
                </Typography>
                <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                  {typeof val === 'number' ? val.toFixed(2) : String(val)}
                </Typography>
              </Box>
            ))}
          </Stack>
        </Paper>
      )}

      {/* SHAP Explanation */}
      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
          Feature importance (SHAP)
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ mb: 2, display: 'block' }}>
          Red bars increase anomaly score · Green bars decrease it
        </Typography>
        <ShapChart data={shapData} />
      </Paper>

      {/* Recommendations */}
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2 }}>
          Recommendations
        </Typography>

        {recommendations.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No recommendations yet
          </Typography>
        ) : (
          <Stack spacing={2} divider={<Divider />}>
            {recommendations.map((rec) => {
              const isPending = rec.status === 'pending';
              const actionPending = approve.isPending || reject.isPending;
              return (
                <Box key={rec.id}>
                  <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                    <Chip
                      label={rec.status}
                      size="small"
                      color={REC_STATUS_COLOR[rec.status] ?? 'default'}
                      sx={{ textTransform: 'capitalize' }}
                    />
                    <Typography variant="caption" color="text.secondary">
                      {formatDate(rec.created_at)}
                    </Typography>
                  </Stack>

                  <Typography variant="body2" sx={{ mb: 1 }}>
                    {rec.explanation}
                  </Typography>

                  <Box
                    component="pre"
                    sx={{
                      p: 1.5,
                      mb: 1,
                      bgcolor: 'action.hover',
                      borderRadius: 1,
                      fontFamily: 'monospace',
                      fontSize: '0.8rem',
                      overflowX: 'auto',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                    }}
                  >
                    {rec.filtered_command}
                  </Box>

                  {isAdmin && isPending && (
                    <Stack direction="row" spacing={1}>
                      <Button
                        startIcon={actionPending ? <CircularProgress size={14} /> : <ApproveIcon />}
                        variant="contained"
                        color="success"
                        size="small"
                        disabled={actionPending}
                        onClick={() => handleApprove(rec.id)}
                      >
                        Approve
                      </Button>
                      <Button
                        startIcon={actionPending ? <CircularProgress size={14} /> : <RejectIcon />}
                        variant="outlined"
                        color="error"
                        size="small"
                        disabled={actionPending}
                        onClick={() => handleReject(rec.id)}
                      >
                        Reject
                      </Button>
                    </Stack>
                  )}

                  {rec.execution_result && Object.keys(rec.execution_result).length > 0 && (
                    <Box sx={{ mt: 1 }}>
                      <Typography variant="caption" color="text.secondary">
                        Execution result:
                      </Typography>
                      <Box
                        component="pre"
                        sx={{
                          p: 1,
                          bgcolor: 'action.hover',
                          borderRadius: 1,
                          fontFamily: 'monospace',
                          fontSize: '0.75rem',
                          overflowX: 'auto',
                          whiteSpace: 'pre-wrap',
                          mt: 0.5,
                        }}
                      >
                        {JSON.stringify(rec.execution_result, null, 2)}
                      </Box>
                    </Box>
                  )}
                </Box>
              );
            })}
          </Stack>
        )}
      </Paper>
    </Box>
  );
}
