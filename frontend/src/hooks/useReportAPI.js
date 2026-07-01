import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8082';

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

// Fetch report data for a specific month
export function useReportData(month) {
  return useQuery({
    queryKey: ['report', month],
    queryFn: async () => {
      const response = await fetchWithTimeout(
        `${API_BASE_URL}/api/data?month=${encodeURIComponent(month)}`
      );
      if (!response.ok) {
        throw new Error('Failed to fetch report data');
      }
      return response.json();
    },
    enabled: !!month,
    staleTime: 0, // always fetch fresh — techno/MIS data changes via separate save flows
  });
}

// Fetch all available months
export function useAvailableMonths() {
  return useQuery({
    queryKey: ['availableMonths'],
    queryFn: async () => {
      const response = await fetchWithTimeout(
        `${API_BASE_URL}/api/available-months`
      );
      if (!response.ok) {
        throw new Error('Failed to fetch available months');
      }
      return response.json();
    },
    staleTime: 1000 * 60 * 60, // 1 hour
  });
}

// Fetch records data
export function useRecordsData(month) {
  return useQuery({
    queryKey: ['records', month],
    queryFn: async () => {
      const response = await fetchWithTimeout(
        `${API_BASE_URL}/api/records?month=${encodeURIComponent(month)}`
      );
      if (!response.ok) {
        throw new Error('Failed to fetch records');
      }
      return response.json();
    },
    enabled: !!month,
  });
}

// Save report data mutation
export function useSaveReportData() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ month, pages }) => {
      const response = await fetch(`${API_BASE_URL}/api/data`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ month, pages }),
      });

      if (!response.ok) {
        throw new Error('Failed to save report data');
      }
      return response.json();
    },
    onSuccess: (_, { month }) => {
      // Invalidate the report data cache so it refetches
      queryClient.invalidateQueries({ queryKey: ['report', month] });
    },
  });
}

// Generate PDF mutation
export function useGeneratePDF() {
  return useMutation({
    mutationFn: async ({ month, pages }) => {
      const response = await fetch(`${API_BASE_URL}/api/generate-pdf`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ month, pages }),
      });

      if (!response.ok) {
        const errBody = await response.json().catch(() => ({}));
        throw new Error(errBody.error || `HTTP ${response.status}`);
      }
      return response.blob();
    },
  });
}

// Upload file mutation
export function useUploadFile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (formData) => {
      const response = await fetch(`${API_BASE_URL}/api/upload-excel`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Failed to upload file');
      }
      return response.json();
    },
    onSuccess: () => {
      // Invalidate report data cache
      queryClient.invalidateQueries({ queryKey: ['report'] });
      queryClient.invalidateQueries({ queryKey: ['records'] });
    },
  });
}
