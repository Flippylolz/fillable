type Boundary = { notify: () => void; paused: boolean; controller: AbortController };
let current: Boundary | undefined;

/** Each authenticated session owns responses from only its request generation. */
export function protectSession(notify: () => void, paused: boolean) {
  current?.controller.abort();
  const boundary = { notify, paused, controller: new AbortController() }; current = boundary;
  return () => { boundary.controller.abort(); if (current === boundary) current = undefined; };
}
function rejected(uncertain = false) {
  return Response.json({ error: { code: uncertain ? "internal_error" : "authentication_required", parameters: {} } },
    { status: uncertain ? 503 : 401, headers: { "Cache-Control": "no-store" } });
}
export async function sessionFetch(request: Request) {
  const boundary = current, authenticated = !new URL(request.url).pathname.startsWith("/api/auth/");
  if (authenticated && boundary?.paused) return rejected();
  const protectedRequest = authenticated && boundary
    ? new Request(request, { signal: AbortSignal.any([request.signal, boundary.controller.signal]) }) : request;
  const response = await fetch(protectedRequest);
  // A discarded response may belong to a committed write; preserve its exact retry.
  if (authenticated && current !== boundary) return rejected(true);
  if (authenticated && response.status === 401) boundary?.notify();
  return response;
}
