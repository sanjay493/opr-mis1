export const dynamic = 'force-dynamic';

export async function GET(request, { params }) {
  const { jobId } = await params;

  try {
    const upstream = await fetch(`http://127.0.0.1:8082/api/generate-pdf/status/${jobId}`);
    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (err) {
    console.error('PDF status proxy error:', err);
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 502,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
