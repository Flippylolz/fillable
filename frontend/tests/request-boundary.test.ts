import { protectSession, sessionFetch } from "../src/accounts/requestBoundary";
const cleanups: (() => void)[] = [];
const protect = (notify = vi.fn(), paused = false) => { const cleanup = protectSession(notify, paused); cleanups.push(cleanup); return cleanup; };
afterEach(() => { for (const cleanup of cleanups.splice(0).reverse()) cleanup(); });
const request = (path = "/api/documents", method = "GET") => new Request(`http://localhost${path}`, { method });

test("only protected unauthorized responses notify the current session; normal data passes untouched", async () => {
  const notify = vi.fn(); protect(notify);
  const data = Response.json({ safe: true });
  const fetcher = vi.fn().mockResolvedValueOnce(data).mockResolvedValueOnce(new Response(null, { status: 403 }))
    .mockResolvedValueOnce(new Response(null, { status: 401 })).mockResolvedValueOnce(new Response(null, { status: 401 }));
  vi.stubGlobal("fetch", fetcher);
  expect(await sessionFetch(request())).toBe(data);
  await sessionFetch(request()); expect(notify).not.toHaveBeenCalled();
  await sessionFetch(request("/api/auth/login", "POST")); expect(notify).not.toHaveBeenCalled();
  await sessionFetch(request()); expect(notify).toHaveBeenCalledTimes(1);
});

test("recovery pauses new application requests while allowing fresh authentication", async () => {
  const notify = vi.fn(); protect(notify, true);
  const fetcher = vi.fn().mockResolvedValue(Response.json({ user: null })); vi.stubGlobal("fetch", fetcher);
  const response = await sessionFetch(request("/api/documents/resource/versions", "POST"));
  expect(response.status).toBe(401); expect(fetcher).not.toHaveBeenCalled(); expect(notify).not.toHaveBeenCalled();
  expect(response.headers.get("Cache-Control")).toBe("no-store");
  await sessionFetch(request("/api/auth/session")); expect(fetcher).toHaveBeenCalledTimes(1);
});

test.each(["replaced", "unmounted", "anonymous"])("late write results from a %s boundary remain uncertain and never notify a new owner", async kind => {
  let finish!: (response: Response) => void;
  const notify = vi.fn(), newer = vi.fn();
  const old = kind === "anonymous" ? () => {} : protect(notify);
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(resolve => { finish = resolve; })));
  const pending = sessionFetch(request("/api/documents/resource/versions", "POST"));
  if (kind !== "unmounted") protect(newer);
  old();
  finish(Response.json({ private_document: "not returned", saved_version_id: "committed" }, { status: 201 }));
  const response = await pending;
  expect(response.status).toBe(503);
  expect(await response.json()).toEqual({ error: { code: "internal_error", parameters: {} } });
  expect(notify).not.toHaveBeenCalled(); expect(newer).not.toHaveBeenCalled();
  if (kind !== "unmounted") {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
    await sessionFetch(request()); expect(newer).toHaveBeenCalledTimes(1);
  }
});

test("requests without an authenticated boundary and network failures preserve their ordinary contract", async () => {
  const response = new Response(null, { status: 401 });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(response).mockRejectedValueOnce(new Error("offline")));
  expect(await sessionFetch(request())).toBe(response);
  await expect(sessionFetch(request())).rejects.toThrow("offline");
});

test("session replacement cancels a response body still being received but not authentication calls", async () => {
  protect();
  let sent!: Request, authentication!: Request;
  vi.stubGlobal("fetch", vi.fn((input: Request) => {
    if (input.url.includes("/api/auth/")) { authentication = input; return Promise.resolve(Response.json({ user: null })); }
    sent = input;
    return Promise.resolve(new Response(new ReadableStream({ start(controller) {
      controller.enqueue(new TextEncoder().encode('{"private":'));
      input.signal.addEventListener("abort", () => controller.error(new Error("obsolete body")));
    } })));
  }));
  const response = await sessionFetch(request());
  const body = response.json();
  const rejectedBody = expect(body).rejects.toThrow("obsolete body");
  await sessionFetch(request("/api/auth/session"));
  protect();
  expect(sent.signal.aborted).toBe(true); expect(authentication.signal.aborted).toBe(false);
  await rejectedBody;
});
