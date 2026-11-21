import { useEffect } from 'react';
import { queryClient } from '../app/queryClient';
import { queryKeys } from './query';

export function useProjectEvents(projectId: string | undefined) {
  useEffect(() => {
    if (!projectId || typeof EventSource === 'undefined') return;
    const base = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
    const events = new EventSource(`${base}/projects/${projectId}/events`, { withCredentials: true });
    const refresh = () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.workspace(projectId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.project(projectId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.exports(projectId) });
    };
    events.addEventListener('message', refresh);
    events.addEventListener('task', refresh);
    return () => events.close();
  }, [projectId]);
}
