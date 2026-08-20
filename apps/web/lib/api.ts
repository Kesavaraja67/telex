/**
 * Typed API client for the FastAPI backend.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
    credentials: "include",
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${path} → ${res.status}: ${text}`);
  }

  return res.json() as Promise<T>;
}

// ── Stats ──────────────────────────────────────────────────────────────────

export interface Stats {
  repos_watched: number;
  prs_opened: number;
  patches_generated: number;
  merge_rate: number;
}

export const getStats = () => apiFetch<Stats>("/api/stats");

// ── Repos ──────────────────────────────────────────────────────────────────

export interface Repo {
  id: string;
  full_name: string;
  default_branch: string;
  is_active: boolean;
  created_at: string;
}

export const getRepos = () => apiFetch<Repo[]>("/api/repos");

export const toggleRepo = (id: string, is_active: boolean) =>
  apiFetch<Repo>(`/api/repos/${id}/toggle`, {
    method: "POST",
    body: JSON.stringify({ is_active }),
  });

// ── Patches ────────────────────────────────────────────────────────────────

export interface PatchSummary {
  id: string;
  package: string;
  old_version: string;
  new_version: string;
  status: "open" | "merged" | "closed";
  pr_url: string | null;
  usages_patched: number;
  opened_at: string;
}

export interface RepoPatchesResponse {
  repo: string;
  patches: PatchSummary[];
}

export const getRepoPatches = (id: string) =>
  apiFetch<RepoPatchesResponse>(`/api/repos/${id}/patches`);

// ── Rescan ─────────────────────────────────────────────────────────────────

export interface RescanPayload {
  package_name: string;
  old_version: string;
  new_version: string;
  changelog?: string;
}

export const triggerRescan = (packageId: string, body: RescanPayload) =>
  apiFetch<{ status: string; package_version_id: string }>(
    `/api/packages/${packageId}/rescan`,
    { method: "POST", body: JSON.stringify(body) }
  );
