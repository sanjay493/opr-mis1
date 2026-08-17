export const dynamic = 'force-dynamic';

export async function GET(request, { params }) {
  const { jobId } = await params;

  try {
    const upstream = await fetch(`http://127.0.0.1:8082/api/generate-pdf/result/${jobId}`);

    if (!upstream.ok) {
      const text = await upstream.text();
      return new Response(text, {
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
    console.error('PDF result proxy error:', err);
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 502,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
