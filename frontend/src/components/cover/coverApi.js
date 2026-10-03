// Client for backend/api_cover.py (selectable report covers + photo library).
const API = process.env.NEXT_PUBLIC_API_URL || '';

export const apiUrl = (path) => `${API}${path}`;

async function call(path, options = {}) {
  const res = await fetch(apiUrl(path), { credentials: 'include', ...options });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`);
  return body;
}

const json = (method, body) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export const coverApi = {
  designs: () => call('/api/cover/designs'),
  settings: (month) => call(`/api/cover/settings?month=${encodeURIComponent(month)}`),
  save: (setting) => call('/api/cover/settings', json('POST', setting)),
  shuffle: (month, design) => call('/api/cover/shuffle', json('POST', { month, design })),
  photos: () => call('/api/cover/photos'),
  upload: (files) => {
    const form = new FormData();
    for (const f of files) form.append('files', f);
    return call('/api/cover/photos', { method: 'POST', body: form });
  },
  remove: (id) => call(`/api/cover/photos/${id}`, { method: 'DELETE' }),
};

export function coverHtmlUrl(month, design, photoId) {
  const q = new URLSearchParams({ month, design });
  if (photoId != null) q.set('photo_id', String(photoId));
  return apiUrl(`/api/cover/html?${q}`);
}
