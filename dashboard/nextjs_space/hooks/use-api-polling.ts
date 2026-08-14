'use client';

import { useState, useEffect, useCallback, useRef } from 'react';

export function useApiPolling<T>(
  fetcher: () => Promise<{ data: T; isMock: boolean }>,
  intervalMs: number = 5000
) {
  const [data, setData] = useState<T | null>(null);
  const [isMock, setIsMock] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const result = await fetcher();
      if (mountedRef.current) {
        setData(result.data);
        setIsMock(result.isMock);
        setError(null);
        setLoading(false);
      }
    } catch (e: any) {
      if (mountedRef.current) {
        setError(e?.message ?? 'Fetch failed');
        setLoading(false);
      }
    }
  }, [fetcher]);

  useEffect(() => {
    mountedRef.current = true;
    refresh();
    const id = setInterval(refresh, intervalMs);
    return () => {
      mountedRef.current = false;
      clearInterval(id);
    };
  }, [refresh, intervalMs]);

  return { data, isMock, loading, error, refresh };
}
