export const dynamic = 'force-dynamic';

export async function POST(request) {
  const body = await request.json();

  const controller = new AbortController();
  // 5-minute timeout — WeasyPrint can be slow for large reports
  const timer = setTimeout(() => controller.abort(), 300_000);

  try {
    const upstream = await fetch('http://127.0.0.1:8082/api/generate-pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    clearTimeout(timer);

    if (!upstream.ok) {
      const text = await upstream.text();
      return new Response(JSON.stringify({ error: text }), {
        status: upstream.status,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const pdfBuffer = await upstream.arrayBuffer();
    const disposition =
      upstream.headers.get('Content-Disposition') ||
      'attachment; filename=SAIL_MIS_Report.pdf';

    return new Response(pdfBuffer, {
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': disposition,
      },
    });
  } catch (err) {
    clearTimeout(timer);
    console.error('PDF proxy error:', err);
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 502,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
