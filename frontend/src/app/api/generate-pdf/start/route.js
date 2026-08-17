export const dynamic = 'force-dynamic';

// Kicks off backend PDF generation and returns immediately with a job_id.
// No timeout needed here — the render itself happens out-of-band on the
// backend; see status/[jobId] and result/[jobId] for polling it.
export async function POST(request) {
  const body = await request.json();

  try {
    const upstream = await fetch('http://127.0.0.1:8082/api/generate-pdf/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (err) {
    console.error('PDF start proxy error:', err);
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 502,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
