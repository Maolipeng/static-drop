/**
 * API client for communicating with the FastAPI backend.
 *
 * - Client-side: authenticated requests go through the Next.js BFF at /console-api/*
 * - Server-side: requests go directly to the FastAPI container via API_INTERNAL_URL
 *   (defaults to http://api:8000 for Docker Compose networking).
 */

const TOKEN = process.env.DEPLOY_TOKEN || "";

/** Base URL for API requests. Empty string = same-origin (client-side / nginx). */
const API_BASE =
  typeof window === "undefined"
    ? process.env.API_INTERNAL_URL || "http://api:8000"
    : "";

export interface Deployment {
  id: string;
  name: string | null;
  url: string;
  url_path: string;
  source_zip: string;
  file_count: number;
  total_size: number;
  created_at: string;
  project_id?: string | null;
  project_name?: string | null;
  project_slug?: string | null;
  version: number;
  is_current?: boolean;
}

export interface Project {
  id: string;
  name: string;
  slug: string;
  current_deployment_id: string | null;
  current_version: number | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectDomain {
  id: string;
  domain: string;
  verified_at: string | null;
  verification_token?: string;
}

export interface DeploymentListResponse {
  deployments: Deployment[];
  total: number;
  limit: number;
  offset: number;
}

export interface DeployResponse extends Deployment {}

export interface ApiError {
  error: string;
  code: string;
}

export interface HealthResponse {
  status: string;
  db: string;
  data_dir: string;
  deployments_dir: string;
}

function authHeaders(): HeadersInit {
  return {
    Authorization: `Bearer ${TOKEN}`,
  };
}

/**
 * Upload a zip file with progress tracking.
 * Uses XMLHttpRequest because fetch doesn't support upload progress.
 */
export function uploadZip(
  file: File,
  name: string | undefined,
  onProgress: (percent: number) => void,
  env?: Record<string, string>,
  projectId?: string,
): Promise<DeployResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("file", file);
    if (name) {
      formData.append("name", name);
    }
    if (projectId) {
      formData.append("project_id", projectId);
    }
    if (env && Object.keys(env).length > 0) {
      formData.append("env", JSON.stringify(env));
    }

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject({ error: "Invalid response from server", code: "INTERNAL" });
        }
      } else {
        try {
          reject(JSON.parse(xhr.responseText));
        } catch {
          reject({ error: `Server error: ${xhr.status}`, code: "INTERNAL" });
        }
      }
    });

    xhr.addEventListener("error", () => {
      reject({ error: "Network error during upload", code: "NETWORK" });
    });

    xhr.addEventListener("abort", () => {
      reject({ error: "Upload aborted", code: "ABORTED" });
    });

    xhr.open("POST", "/console-api/deploy");
    xhr.send(formData);
  });
}

/**
 * Upload a folder (multiple files with preserved directory structure).
 * Uses webkitRelativePath to encode each file's path within the folder.
 * Falls back to file.name if webkitRelativePath is empty.
 */
export function uploadFolder(
  files: File[],
  name: string | undefined,
  onProgress: (percent: number) => void,
  env?: Record<string, string>,
  projectId?: string,
): Promise<DeployResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();

    for (const file of files) {
      // webkitRelativePath includes the top-level folder name, e.g. "dist/index.html"
      // The server uses this to reconstruct the directory structure.
      const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
      // Use the third arg to set the filename to the relative path
      formData.append("files", file, relativePath);
    }

    if (name) {
      formData.append("name", name);
    }
    if (projectId) {
      formData.append("project_id", projectId);
    }
    if (env && Object.keys(env).length > 0) {
      formData.append("env", JSON.stringify(env));
    }

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject({ error: "Invalid response from server", code: "INTERNAL" });
        }
      } else {
        try {
          reject(JSON.parse(xhr.responseText));
        } catch {
          reject({ error: `Server error: ${xhr.status}`, code: "INTERNAL" });
        }
      }
    });

    xhr.addEventListener("error", () => {
      reject({ error: "Network error during upload", code: "NETWORK" });
    });

    xhr.addEventListener("abort", () => {
      reject({ error: "Upload aborted", code: "ABORTED" });
    });

    xhr.open("POST", "/console-api/deploy-folder");
    xhr.send(formData);
  });
}

export async function deployGithub(
  repository: string,
  ref: string | undefined,
  name: string | undefined,
  projectId: string | undefined,
): Promise<DeployResponse> {
  const formData = new FormData();
  formData.append("repository", repository);
  if (ref) formData.append("ref", ref);
  if (name) formData.append("name", name);
  if (projectId) formData.append("project_id", projectId);
  const res = await fetch("/console-api/github/deploy", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function listDeployments(
  limit = 50,
  offset = 0,
): Promise<DeploymentListResponse> {
  const res = await fetch(`${API_BASE}/api/deployments?limit=${limit}&offset=${offset}`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    throw await res.json();
  }
  return res.json();
}

export async function listProjects(): Promise<{ projects: Project[] }> {
  const res = await fetch("/console-api/projects", { cache: "no-store" });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function rollbackProject(projectId: string, version: number): Promise<Deployment> {
  const res = await fetch(`/console-api/projects/${encodeURIComponent(projectId)}/rollback/${version}`, { method: "POST" });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function addProjectDomain(projectId: string, domain: string): Promise<ProjectDomain & { verification: { name: string; value: string } }> {
  const res = await fetch(`/console-api/projects/${encodeURIComponent(projectId)}/domains`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ domain }) });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function provisionProjectDomain(projectId: string, domain: string): Promise<ProjectDomain & { dns_records: unknown[] }> {
  const res = await fetch(`/console-api/projects/${encodeURIComponent(projectId)}/domains/provision`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ domain }) });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function verifyProjectDomain(domainId: string): Promise<void> {
  const res = await fetch(`/console-api/domains/${encodeURIComponent(domainId)}/verify`, { method: "POST" });
  if (!res.ok) throw await res.json();
}

export async function deleteProjectDomain(domainId: string): Promise<void> {
  const res = await fetch(`/console-api/domains/${encodeURIComponent(domainId)}`, { method: "DELETE" });
  if (!res.ok) throw await res.json();
}

export async function getDeployment(id: string): Promise<Deployment> {
  const res = await fetch(`${API_BASE}/api/deployments/${id}`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    throw await res.json();
  }
  return res.json();
}

export async function deleteDeployment(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/deployments/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) {
    throw await res.json();
  }
}

export async function checkHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) {
    throw await res.json();
  }
  return res.json();
}

/**
 * Upload with progress via fetch (used as fallback or for tests).
 * Not used in the UI — uploadZip is preferred for progress events.
 */
export async function uploadZipFetch(
  file: File,
  name?: string,
): Promise<DeployResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (name) formData.append("name", name);

  const res = await fetch("/console-api/deploy", {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw await res.json();
  }
  return res.json();
}

/**
 * Format bytes to human-readable string.
 */
export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

/**
 * Format ISO timestamp to readable date.
 */
export function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
