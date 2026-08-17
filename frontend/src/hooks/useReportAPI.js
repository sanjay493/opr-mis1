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

// Fetch report data for every page of a month in one shot. Slow (~20-40s —
// each page's own DB calls run serially server-side), so the report viewer
// only calls this on demand (PDF export, which needs every page at once);
// see useReportPage for the fast per-page fetch preview navigation uses.
export function useReportData(month, options = {}) {
  return useQuery({
    queryKey: ['report', month],
    queryFn: async () => {
      const response = await fetchWithTimeout(
        `${API_BASE_URL}/api/data?month=${encodeURIComponent(month)}`,
        {},
        60000 // full report spans ~40 pages' worth of DB calls — needs more room than the 30s default
      );
      if (!response.ok) {
        throw new Error('Failed to fetch report data');
      }
      return response.json();
    },
    enabled: !!month && options.enabled !== false,
    staleTime: 0, // always fetch fresh — techno/MIS data changes via separate save flows
  });
}

// Fetch a single page's report data — each page only depends on its own DB
// calls server-side, so this is typically well under a second even though
// the full-month fetch above takes 20-40s. Used for the report preview so
// switching months/pages doesn't wait on every page to compute.
export function useReportPage(month, pageNumber, options = {}) {
  return useQuery({
    queryKey: ['report-page', month, pageNumber],
    queryFn: async () => {
      const response = await fetchWithTimeout(
        `${API_BASE_URL}/api/data?month=${encodeURIComponent(month)}&page_number=${pageNumber}`
      );
      if (!response.ok) {
        throw new Error('Failed to fetch report page');
      }
      const data = await response.json();
      return data[0];
    },
    enabled: !!month && !!pageNumber && options.enabled !== false,
    staleTime: 0,
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

// Save Page 3 Production Narrative + Highlights, keyed by report month
export function useSavePage3Narrative() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ month, production_narrative, highlights }) => {
      const response = await fetch(`${API_BASE_URL}/api/page3-narrative`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ month, production_narrative, highlights }),
      });

      if (!response.ok) {
        throw new Error('Failed to save narrative');
      }
      return response.json();
    },
    onSuccess: (_, { month }) => {
      queryClient.invalidateQueries({ queryKey: ['report', month] });
    },
  });
}

// Generate PDF mutation. A full report render takes 20+ minutes, so this
// doesn't hold one HTTP request open for that whole time: it starts a
// backend job, polls status until done/error, then fetches the finished
// PDF. Decouples render time from any client/proxy timeout.
const PDF_POLL_INTERVAL_MS = 4000;

async function throwForErrorResponse(response) {
  const errBody = await response.json().catch(() => ({}));
  throw new Error(errBody.error || errBody.detail || `HTTP ${response.status}`);
}

export function useGeneratePDF() {
  return useMutation({
    mutationFn: async ({ month, pages }) => {
      const startRes = await fetch(`${API_BASE_URL}/api/generate-pdf/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ month, pages }),
      });
      if (!startRes.ok) await throwForErrorResponse(startRes);
      const { job_id } = await startRes.json();

      // eslint-disable-next-line no-constant-condition
      while (true) {
        await new Promise((resolve) => setTimeout(resolve, PDF_POLL_INTERVAL_MS));
        const statusRes = await fetch(`${API_BASE_URL}/api/generate-pdf/status/${job_id}`);
        if (!statusRes.ok) await throwForErrorResponse(statusRes);
        const statusBody = await statusRes.json();
        if (statusBody.status === 'error') {
          throw new Error(statusBody.error || 'PDF generation failed');
        }
        if (statusBody.status === 'done') break;
        // else "pending" — keep polling
      }

      const resultRes = await fetch(`${API_BASE_URL}/api/generate-pdf/result/${job_id}`);
      if (!resultRes.ok) await throwForErrorResponse(resultRes);
      return resultRes.blob();
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
