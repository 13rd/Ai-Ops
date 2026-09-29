import { Button, ButtonGroup } from '@mui/material';
import type { TimeRange } from '@/entities/Metric';

const RANGES: { value: TimeRange; label: string }[] = [
  { value: '1h', label: '1h' },
  { value: '24h', label: '24h' },
  { value: '7d', label: '7d' },
  { value: '30d', label: '30d' },
];

interface Props {
  value: TimeRange;
  onChange: (range: TimeRange) => void;
}

export function TimeRangeSelector({ value, onChange }: Props) {
  return (
    <ButtonGroup size="small" variant="outlined">
      {RANGES.map((r) => (
        <Button
          key={r.value}
          variant={value === r.value ? 'contained' : 'outlined'}
          onClick={() => onChange(r.value)}
        >
          {r.label}
        </Button>
      ))}
    </ButtonGroup>
  );
}
