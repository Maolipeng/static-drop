import { cookies } from "next/headers";
import type { Deployment, DeploymentListResponse, HealthResponse, Project, ProjectDomain } from "@/lib/api";

const API_BASE = process.env.API_INTERNAL_URL || "http://api:8000";
const TOKEN = process.env.DEPLOY_TOKEN || "";

async function authHeaders(): Promise<HeadersInit> {
  const session = (await cookies()).get("staticdrop_session")?.value;
  return session
    ? { Cookie: `staticdrop_session=${encodeURIComponent(session)}` }
    : { Authorization: `Bearer ${TOKEN}` };
}

export async function listDeployments(limit = 50, offset = 0): Promise<DeploymentListResponse> {
  const res = await fetch(`${API_BASE}/api/deployments?limit=${limit}&offset=${offset}`, {
    headers: await authHeaders(),
    cache: "no-store",
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function getDeployment(id: string): Promise<Deployment> {
  const res = await fetch(`${API_BASE}/api/deployments/${id}`, {
    headers: await authHeaders(),
    cache: "no-store",
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function checkHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/api/health`, { cache: "no-store" });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function getProjectDeployments(projectId: string): Promise<{ project: Project; deployments: Deployment[] }> {
  const res = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projectId)}/deployments`, { headers: await authHeaders(), cache: "no-store" });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function getProjectDomains(projectId: string): Promise<ProjectDomain[]> {
  const res = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projectId)}/domains`, { headers: await authHeaders(), cache: "no-store" });
  if (!res.ok) throw await res.json();
  return (await res.json()).domains;
}
