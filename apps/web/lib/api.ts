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

// ── Engine B — Recovery ─────────────────────────────────────────────────────

export interface RecoveryEvent {
  id: string;
  payment_attempt_id: string;
  failure_type: string;
  classification: "transient" | "code_defect" | "unknown";
  action_taken: string;
  llm_provider: string;
  llm_model: string;
  outcome: "recovered" | "escalated" | "unresolved";
  pull_request_id: string | null;
  detected_at: string;
  resolved_at: string | null;
}

export interface RecoveryStats {
  total_payment_attempts: number;
  total_recovery_events: number;
  recovered: number;
  escalated: number;
  unresolved: number;
  recovery_rate: number;
  tier1_classified: number;
  tier2_classified: number;
}

export const getRecoveryStats = () =>
  apiFetch<RecoveryStats>("/api/recovery/stats");

export const getRecoveryEvents = (limit = 50, offset = 0) =>
  apiFetch<RecoveryEvent[]>(`/api/recovery/events?limit=${limit}&offset=${offset}`);

// ── Engine B — Payments ─────────────────────────────────────────────────────

export interface BatchRunPayload {
  count: number;
  failure_rate: number;
  client_request_id?: string;
}

export interface BatchRunResponse {
  status: "created" | "existing";
  payment_attempt_ids: string[];
}

export const triggerBatchRun = (body: BatchRunPayload) =>
  apiFetch<BatchRunResponse>("/api/payments/batch-run", {
    method: "POST",
    body: JSON.stringify(body),
  });
