import type { ListResponse } from '../types';

export function items<T>(response: ListResponse<T> | undefined): T[] {
  if (!response) return [];
  return Array.isArray(response) ? response : response.items;
}

export function total<T>(response: ListResponse<T> | undefined): number {
  if (!response) return 0;
  return Array.isArray(response) ? response.length : response.total ?? response.items.length;
}

export const queryKeys = {
  me: ['auth', 'me'] as const,
  projects: ['projects'] as const,
  project: (id: string) => ['projects', id] as const,
  workspace: (id: string) => ['projects', id, 'workspace'] as const,
  requirements: (id: string) => ['projects', id, 'requirements'] as const,
  risks: (id: string) => ['projects', id, 'risks'] as const,
  scores: (id: string) => ['projects', id, 'scores'] as const,
  candidates: (id: string) => ['sections', id, 'candidates'] as const,
  snapshots: (id: string) => ['projects', id, 'snapshots'] as const,
  exports: (id: string) => ['projects', id, 'exports'] as const,
};

export function isActiveTask(status: string | undefined) {
  return status === 'queued' || status === 'running' || status === 'pending' || status === 'started';
}
