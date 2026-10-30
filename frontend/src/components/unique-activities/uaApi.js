// Client for /api/unique-activities (backend/api_unique_activity.py).

const API = process.env.NEXT_PUBLIC_API_URL || '';
const BASE = `${API}/api/unique-activities`;

async function call(url, opts) {
  const res = await fetch(url, opts);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = body.detail;
    throw new Error(typeof d === 'string' ? d : `Request failed (${res.status})`);
  }
  return body;
}

const post = (url, data) => call(url, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: data ? JSON.stringify(data) : undefined,
});

export const uaApi = {
  // filters: { q, tag, plant, from, to } — empty values are left out
  list: (filters = {}) => {
    const params = new URLSearchParams(Object.entries(filters).filter(([, v]) => v));
    return call(`${BASE}?${params}`).then((d) => d.activities);
  },
  tags: () => call(`${BASE}/tags`),
  add: (activity) => post(`${BASE}/add`, activity),
  update: (id, activity) => post(`${BASE}/${id}/update`, activity),
  remove: (id) => post(`${BASE}/${id}/delete`),
};

const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// 'YYYY-MM-DD' -> '16 Jul 2026'
export function fmtActivityDate(d) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d || '');
  return m ? `${Number(m[3])} ${MON[Number(m[2]) - 1]} ${m[1]}` : (d || '');
}
