/** Existing workspace tests grant editing explicitly; lease failures have their own tests. */
export async function leaseResponse(request: Request) {
  const body = await request.clone().json();
  return Response.json({ status: body.action === "release" ? "released" : "active", source_version_id: body.source_version_id,
    lease_id: "33333333-3333-4333-8333-333333333333", expires_at: new Date(Date.now() + 60000).toISOString(), valid_for_seconds: 60 });
}
