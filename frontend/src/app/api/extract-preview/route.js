export const dynamic = 'force-dynamic';

export async function POST(request) {
  const contentType = request.headers.get('content-type') || '';

  const controller = new AbortController();
  // 6-minute timeout — DSP PDFs with special steel tables can take up to 5 min
  const timer = setTimeout(() => controller.abort(), 360_000);

  try {
    const body = await request.arrayBuffer();

    const upstream = await fetch('http://127.0.0.1:8082/api/extract-preview', {
      method: 'POST',
      headers: { 'Content-Type': contentType },
      body,
      signal: controller.signal,
    });

    clearTimeout(timer);

    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: { 'Content-Type': upstream.headers.get('content-type') || 'application/json' },
    });
  } catch (err) {
    clearTimeout(timer);
    console.error('extract-preview proxy error:', err);
    return new Response(
      JSON.stringify({ detail: `Proxy error: ${String(err)}` }),
      { status: 502, headers: { 'Content-Type': 'application/json' } },
    );
  }
}
