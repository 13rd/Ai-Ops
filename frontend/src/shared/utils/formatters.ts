import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import utc from 'dayjs/plugin/utc';

dayjs.extend(relativeTime);
dayjs.extend(utc);

function parseUtc(date: string): dayjs.Dayjs {
  return dayjs.utc(date).local();
}

export function fromNow(date: string | null | undefined): string {
  if (!date) return 'Never';
  return parseUtc(date).fromNow();
}

export function formatDate(date: string | null | undefined): string {
  if (!date) return '—';
  return parseUtc(date).format('YYYY-MM-DD HH:mm');
}
