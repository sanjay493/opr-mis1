'use client';

import { useState, useEffect, useCallback } from 'react';

/**
 * Hook to fetch or calculate SAIL SMS parameters (Hot Metal Consumption, Scrap Consumption)
 * Uses API endpoint that either retrieves from DB or calculates on-the-fly using weighted average.
 *
 * Usage:
 *   const { sailParams, loading, error } = useSailSmsParams(apiBase, month);
 */
export function useSailSmsParams(apiBase, month) {
  const [sailParams, setSailParams] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchSailParams = useCallback(async () => {
    console.log('[useSailSmsParams] fetchSailParams called. month:', month, 'apiBase:', apiBase);

    if (!month) {
      console.log('[useSailSmsParams] Skipping - missing month');
      setSailParams({});
      return;
    }

    if (!apiBase) {
      console.log('[useSailSmsParams] Warning: apiBase is empty, cannot fetch SAIL params');
      setError('API base URL not configured');
      setSailParams({});
      return;
    }

    console.log('[useSailSmsParams] Starting fetch for month:', month);
    setLoading(true);
    setError(null);

    try {
      const url = `${apiBase}/api/sail-sms-params?month=${encodeURIComponent(month)}`;
      console.log('[useSailSmsParams] Fetch URL:', url);

      const response = await fetch(url);
      console.log('[useSailSmsParams] Response status:', response.status, 'ok:', response.ok);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      console.log('[useSailSmsParams] Full response data:', data);
      console.log('[useSailSmsParams] sail_params:', data.sail_params);

      const params = data.sail_params || {};
      console.log('[useSailSmsParams] Setting sailParams to:', params);
      setSailParams(params);
    } catch (err) {
      console.error('[useSailSmsParams] Error:', err.message, err.stack);
      setError(err.message);
      setSailParams({});
    } finally {
      setLoading(false);
    }
  }, [apiBase, month]);

  useEffect(() => {
    fetchSailParams();
  }, [fetchSailParams]);

  return { sailParams, loading, error, refetch: fetchSailParams };
}

/**
 * Format SAIL parameter value with source indicator
 */
export function formatSailValue(param, key) {
  if (!param) return { value: null, source: null };

  const value = param[key]; // 'actual' or 'till_month_actual'
  if (value === null || value === undefined) {
    return { value: null, source: null };
  }

  return {
    value: typeof value === 'number' ? value.toFixed(2) : value,
    source: param.source || 'unknown'
  };
}
