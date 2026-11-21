import dayjs from 'dayjs';

export const dateTime = (value?: string) => (value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '—');
export const date = (value?: string) => (value ? dayjs(value).format('YYYY-MM-DD') : '—');

export const projectStatus: Record<string, { label: string; color: string }> = {
  draft: { label: '待上传', color: 'default' },
  uploaded: { label: '待解析', color: 'blue' },
  parsing: { label: '解析中', color: 'processing' },
  analyzing: { label: '分析中', color: 'processing' },
  workspace: { label: '编写中', color: 'blue' },
  review: { label: '审阅中', color: 'gold' },
  completed: { label: '已完成', color: 'green' },
  archived: { label: '已归档', color: 'default' },
};

export const taskStatus: Record<string, { label: string; color: string }> = {
  queued: { label: '排队中', color: 'default' },
  pending: { label: '排队中', color: 'default' },
  running: { label: '执行中', color: 'processing' },
  started: { label: '执行中', color: 'processing' },
  succeeded: { label: '已完成', color: 'success' },
  failed: { label: '失败', color: 'error' },
  cancelled: { label: '已取消', color: 'default' },
};

export const reviewStatus: Record<string, { label: string; color: string }> = {
  confirmed: { label: '已确认', color: 'green' },
  unconfirmed: { label: '待确认', color: 'blue' },
  needs_review: { label: '待复核', color: 'gold' },
  gap: { label: '有缺口', color: 'red' },
  empty: { label: '待补内容', color: 'default' },
};

export function displayJson(value: unknown) {
  if (value === undefined || value === null) return '—';
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
}
