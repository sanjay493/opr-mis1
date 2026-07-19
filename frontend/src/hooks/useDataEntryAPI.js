import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

const fetchWithTimeout = (url, options = {}, timeoutMs = 30000) => {
  return new Promise((resolve, reject) => {
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      ctrl.abort();
      reject(new Error(`Request timed out after ${timeoutMs}ms: ${url}`));
    }, timeoutMs);
    fetch(url, { ...options, signal: ctrl.signal })
      .then((res) => {
        clearTimeout(t);
        resolve(res);
      })
      .catch((err) => {
        clearTimeout(t);
        reject(err);
      });
  });
};

// Stock Data Hooks
export function useStockData(plant, stockMonth, enabled = true) {
  return useQuery({
    queryKey: ['stock', plant, stockMonth],
    queryFn: async () => {
      const response = await fetchWithTimeout(
        `${API_BASE_URL}/api/stock-data?plant=${encodeURIComponent(plant)}&stock_month=${encodeURIComponent(stockMonth)}`
      );
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    },
    enabled: enabled && !!plant && !!stockMonth,
    staleTime: 1000 * 60 * 5, // 5 minutes for data-entry
  });
}

export function useSaveStockEntry() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ entries }) => {
      const response = await fetch(`${API_BASE_URL}/api/stock-entry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entries }),
      });
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    },
    onSuccess: (_, { entries }) => {
      // Invalidate stock data for all affected plant/month combinations
      entries.forEach(entry => {
        queryClient.invalidateQueries({
          queryKey: ['stock', entry.plant, entry.stock_month],
        });
      });
    },
  });
}

// Conversion Data Hooks
export function useConversionData(fyStart, enabled = true) {
  return useQuery({
    queryKey: ['conversion', fyStart],
    queryFn: async () => {
      const response = await fetchWithTimeout(
        `${API_BASE_URL}/api/conversion-data?fy_start=${fyStart}`
      );
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    },
    enabled: enabled && !!fyStart,
    staleTime: 1000 * 60 * 5,
  });
}

export function useSaveConversion() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ fyStart, entries }) => {
      const response = await fetch(`${API_BASE_URL}/api/conversion-data`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(entries),
      });
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    },
    onSuccess: (_, { fyStart }) => {
      queryClient.invalidateQueries({ queryKey: ['conversion', fyStart] });
    },
  });
}

// Opening Stock Hooks
export function useOpeningStockData(plant, month, enabled = true) {
  return useQuery({
    queryKey: ['opening-stock', plant, month],
    queryFn: async () => {
      const response = await fetchWithTimeout(
        `${API_BASE_URL}/api/opening-stock?plant=${encodeURIComponent(plant)}&month=${encodeURIComponent(month)}`
      );
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    },
    enabled: enabled && !!plant && !!month,
    staleTime: 1000 * 60 * 5,
  });
}

export function useSaveOpeningStock() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ plant, month, entries }) => {
      const response = await fetch(`${API_BASE_URL}/api/opening-stock`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plant, month, entries }),
      });
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    },
    onSuccess: (_, { plant, month }) => {
      queryClient.invalidateQueries({
        queryKey: ['opening-stock', plant, month],
      });
    },
  });
}

// IPT (Inter-Plant Transfer) Hooks
export function useIPTData(month, enabled = true) {
  return useQuery({
    queryKey: ['ipt', month],
    queryFn: async () => {
      const response = await fetchWithTimeout(
        `${API_BASE_URL}/api/ipt?month=${encodeURIComponent(month)}`
      );
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    },
    enabled: enabled && !!month,
    staleTime: 1000 * 60 * 5,
  });
}

export function useSaveIPT() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ month, entries }) => {
      const response = await fetch(`${API_BASE_URL}/api/ipt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ month, entries }),
      });
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    },
    onSuccess: (_, { month }) => {
      queryClient.invalidateQueries({ queryKey: ['ipt', month] });
    },
  });
}

// Targets Hooks
export function useTargetsData(fyStart, plant, enabled = true) {
  return useQuery({
    queryKey: ['targets', fyStart, plant],
    queryFn: async () => {
      const response = await fetchWithTimeout(
        `${API_BASE_URL}/api/targets?fy_start=${fyStart}&plant=${encodeURIComponent(plant)}`
      );
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    },
    enabled: enabled && !!fyStart && !!plant,
    staleTime: 1000 * 60 * 5,
  });
}

export function useSaveTargets() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ fyStart, plant, entries }) => {
      const response = await fetch(`${API_BASE_URL}/api/targets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fy_start: fyStart, plant, entries }),
      });
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    },
    onSuccess: (_, { fyStart, plant }) => {
      queryClient.invalidateQueries({ queryKey: ['targets', fyStart, plant] });
    },
  });
}
