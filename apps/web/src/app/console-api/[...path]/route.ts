import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const API_BASE = process.env.API_INTERNAL_URL || process.env.API_URL || "http://api:8000";
const DEPLOY_TOKEN = process.env.DEPLOY_TOKEN || "";

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (!path.length || path.some((part) => part === ".." || part.includes("\\"))) {
    return NextResponse.json({ error: "Invalid API path", code: "VALIDATION_ERROR" }, { status: 400 });
  }

  const upstreamUrl = `${API_BASE}/api/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  const accept = request.headers.get("accept");
  if (contentType) headers.set("content-type", contentType);
  if (accept) headers.set("accept", accept);
  const session = request.cookies.get("staticdrop_session")?.value;
  if (session) {
    headers.set("cookie", `staticdrop_session=${encodeURIComponent(session)}`);
  } else if (!(path.length === 2 && path[0] === "auth" && path[1] === "me")) {
    headers.set("authorization", `Bearer ${DEPLOY_TOKEN}`);
  }

  const init: RequestInit & { duplex?: "half" } = {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
    cache: "no-store",
    duplex: "half",
  };

  const response = await fetch(upstreamUrl, init);
  const responseHeaders = new Headers();
  const responseContentType = response.headers.get("content-type");
  if (responseContentType) responseHeaders.set("content-type", responseContentType);
  const setCookie = response.headers.get("set-cookie");
  if (setCookie) responseHeaders.set("set-cookie", setCookie);
  return new NextResponse(response.body, {
    status: response.status,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const DELETE = proxy;
