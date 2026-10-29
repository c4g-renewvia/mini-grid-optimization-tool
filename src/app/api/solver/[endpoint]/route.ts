import { NextResponse } from 'next/server';

const methods = new Map([
  ['solvers', 'GET'],
  ['solve', 'POST'],
  ['local_optimization', 'POST'],
]);

type RouteContext = { params: Promise<{ endpoint: string }> };

async function proxy(request: Request, { params }: RouteContext) {
  const { endpoint } = await params;
  const method = methods.get(endpoint);
  if (!method) {
    return NextResponse.json(
      { detail: 'Unknown solver endpoint' },
      { status: 404 }
    );
  }
  if (request.method !== method) {
    return NextResponse.json(
      { detail: 'Method not allowed' },
      { status: 405, headers: { Allow: method } }
    );
  }

  const backendUrl =
    process.env.BACKEND_URL?.trim() ||
    (process.env.NODE_ENV !== 'production' ||
    process.env.OFFLINE_MODE === 'true'
      ? 'http://localhost:8000'
      : '');

  if (!backendUrl) {
    console.error('BACKEND_URL is not configured for the solver API.');
    return NextResponse.json(
      {
        detail:
          'Solver backend is not configured. Set BACKEND_URL on the server.',
      },
      { status: 503 }
    );
  }

  let url: URL;
  try {
    url = new URL(`${backendUrl.replace(/\/+$/, '')}/${endpoint}`);
    if (!['http:', 'https:'].includes(url.protocol)) {
      throw new Error('BACKEND_URL must use HTTP or HTTPS.');
    }
    url.search = new URL(request.url).search;
  } catch (error) {
    console.error('Invalid solver BACKEND_URL:', error);
    return NextResponse.json(
      { detail: 'Solver backend configuration is invalid.' },
      { status: 503 }
    );
  }

  try {
    const response = await fetch(url, {
      method,
      headers: method === 'POST' ? { 'Content-Type': 'application/json' } : {},
      body: method === 'POST' ? await request.text() : undefined,
      cache: 'no-store',
      signal: request.signal,
      redirect: 'error',
    });

    return new Response(response.body, {
      status: response.status,
      headers: {
        'Content-Type':
          response.headers.get('Content-Type') || 'application/json',
        'Cache-Control': 'no-store',
      },
    });
  } catch (error) {
    console.error('Solver backend request failed:', error);
    return NextResponse.json(
      { detail: 'Could not reach the solver backend. Please try again later.' },
      { status: 502 }
    );
  }
}

export { proxy as GET, proxy as POST };
