import assert from 'node:assert/strict';
import { mock, test } from 'node:test';
import { GET, POST } from './route';

test('solver proxy forwards only supported requests and reports backend failures', async () => {
  const originalEnv = {
    BACKEND_URL: process.env.BACKEND_URL,
    NODE_ENV: process.env.NODE_ENV,
    OFFLINE_MODE: process.env.OFFLINE_MODE,
  };
  const errors = mock.method(console, 'error', () => {});
  const upstream = mock.method(globalThis, 'fetch', async () =>
    Response.json([{ name: 'SimpleMSTSolver', params: [] }])
  );
  const context = (endpoint: string) => ({
    params: Promise.resolve({ endpoint }),
  });
  const request = (endpoint: string, method = 'GET', body?: string) =>
    new Request(`https://hosted.example/api/solver/${endpoint}?t=123`, {
      method,
      body,
      headers: { Cookie: 'private-session=not-forwarded' },
    });

  try {
    Object.assign(process.env, {
      NODE_ENV: 'production',
      OFFLINE_MODE: 'false',
      BACKEND_URL: 'https://backend.example/api/',
    });
    const response = await GET(request('solvers'), context('solvers'));
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('Cache-Control'), 'no-store');
    assert.deepEqual(await response.json(), [
      { name: 'SimpleMSTSolver', params: [] },
    ]);
    const firstCall = upstream.mock.calls[0];
    assert.equal(
      String(firstCall.arguments[0]),
      'https://backend.example/api/solvers?t=123'
    );
    assert.deepEqual(firstCall.arguments[1]?.headers, {});
    assert.equal(firstCall.arguments[1]?.cache, 'no-store');

    upstream.mock.mockImplementation(async () =>
      Response.json({ detail: 'Need at least 2 nodes' }, { status: 422 })
    );
    for (const endpoint of ['solve', 'local_optimization']) {
      const body = JSON.stringify({ nodes: [] });
      const result = await POST(
        request(endpoint, 'POST', body),
        context(endpoint)
      );
      assert.equal(result.status, 422);
      assert.deepEqual(await result.json(), {
        detail: 'Need at least 2 nodes',
      });
      const call = upstream.mock.calls.at(-1)!;
      assert.equal(
        String(call.arguments[0]),
        `https://backend.example/api/${endpoint}?t=123`
      );
      assert.equal(call.arguments[1]?.body, body);
      assert.equal(call.arguments[1]?.method, 'POST');
      assert.deepEqual(call.arguments[1]?.headers, {
        'Content-Type': 'application/json',
      });
    }

    const calls = upstream.mock.callCount();
    assert.equal(
      (await GET(request('unknown'), context('unknown'))).status,
      404
    );
    const wrongMethod = await GET(request('solve'), context('solve'));
    assert.equal(wrongMethod.status, 405);
    assert.equal(wrongMethod.headers.get('Allow'), 'POST');
    assert.equal(upstream.mock.callCount(), calls);

    delete process.env.BACKEND_URL;
    const missingConfig = await GET(request('solvers'), context('solvers'));
    assert.equal(missingConfig.status, 503);
    assert.match((await missingConfig.json()).detail, /BACKEND_URL/);
    assert.equal(upstream.mock.callCount(), calls);

    for (const backendUrl of ['invalid-url', 'file:///tmp/backend']) {
      process.env.BACKEND_URL = backendUrl;
      assert.equal(
        (await GET(request('solvers'), context('solvers'))).status,
        503
      );
      assert.equal(upstream.mock.callCount(), calls);
    }

    delete process.env.BACKEND_URL;
    Object.assign(process.env, { NODE_ENV: 'development' });
    await GET(request('solvers'), context('solvers'));
    assert.equal(
      String(upstream.mock.calls.at(-1)!.arguments[0]),
      'http://localhost:8000/solvers?t=123'
    );

    Object.assign(process.env, {
      NODE_ENV: 'production',
      OFFLINE_MODE: 'true',
    });
    await GET(request('solvers'), context('solvers'));
    assert.equal(
      String(upstream.mock.calls.at(-1)!.arguments[0]),
      'http://localhost:8000/solvers?t=123'
    );

    upstream.mock.mockImplementation(async () => {
      throw new TypeError('fetch failed');
    });
    assert.equal(
      (await GET(request('solvers'), context('solvers'))).status,
      502
    );
  } finally {
    for (const [name, value] of Object.entries(originalEnv)) {
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    }
    upstream.mock.restore();
    errors.mock.restore();
  }
});
