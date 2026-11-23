import { useEffect, useState } from 'react';
import { getDashboard } from '../services/api';
import type { DashboardData } from '../types/dashboard';

type DashboardState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'ready'; data: DashboardData };

export function useDashboard() {
  const [state, setState] = useState<DashboardState>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getDashboard(controller.signal).then(
      data => { if (!controller.signal.aborted) setState({ status: 'ready', data }); },
      () => { if (!controller.signal.aborted) setState({ status: 'error' }); },
    );
    return () => controller.abort();
  }, [attempt]);

  function refresh() {
    setState({ status: 'loading' });
    setAttempt(value => value + 1);
  }

  return { state, refresh };
}
