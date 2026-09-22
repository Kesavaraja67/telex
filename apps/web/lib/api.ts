/**
 * Typed API client for the FastAPI backend.
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getApiUrl(): string {
  return API_BASE;
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const reqHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options?.headers as Record<string, string>) ?? {}),
  };

  if (typeof window !== "undefined") {
    const token = localStorage.getItem("telex_token");
    if (token && !reqHeaders["Authorization"]) {
      reqHeaders["Authorization"] = `Bearer ${token}`;
    }
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: reqHeaders,
    credentials: "include",
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${path} → ${res.status}: ${text}`);
  }

  return res.json() as Promise<T>;
}

// ── Stats ──────────────────────────────────────────────────────────────────

export interface DetectedChangeSummary {
  id: string;
  symbol_old: string;
  symbol_new?: string | null;
  change_type: string;
  description: string;
  created_at: string;
}

export interface Stats {
  repos_watched: number;
  prs_opened: number;
  patches_generated: number;
  merge_rate: number;
  recent_changes?: DetectedChangeSummary[];
}

export const getStats = () => apiFetch<Stats>("/api/stats");

// ── Repos ──────────────────────────────────────────────────────────────────

export interface CommitInfo {
  hash: string;
  short_hash: string;
  message: string;
  author: string;
  email?: string;
  date: string;
  relative_time: string;
}

export interface Repo {
  id: string;
  full_name: string;
  name?: string;
  owner?: string;
  description?: string;
  default_branch: string;
  is_active: boolean;
  requires_tests?: boolean;
  requires_typecheck?: boolean;
  created_at: string;
  github_url: string;
  languages?: string[];
  patch_count?: number;
  status?: string;
  last_commit?: CommitInfo;
  dependencies?: string[];
}

export interface RepoDetails extends Repo {
  commits: CommitInfo[];
}

export interface CommitInsight {
  hash: string;
  impact: string;
  risk_level: string;
}

export interface AIExplanation {
  summary: string;
  commit_insights: CommitInsight[];
  architecture_verdict: string;
  risk_score: number;
  recommended_actions: string[];
}

export const getRepos = (sync: boolean = false, includeBenchmarks: boolean = false) => {
  const params = new URLSearchParams();
  if (sync) params.set("sync", "true");
  if (includeBenchmarks) params.set("include_benchmarks", "true");
  const qs = params.toString();
  return apiFetch<Repo[]>(qs ? `/api/repos?${qs}` : "/api/repos");
};

export const syncRepos = (includeBenchmarks: boolean = false) => {
  const qs = includeBenchmarks ? "?include_benchmarks=true" : "";
  return apiFetch<Repo[]>(`/api/repos/sync${qs}`, { method: "POST" });
};

export const getRepoDetails = (id: string) => apiFetch<RepoDetails>(`/api/repos/${id}`);

export const explainRepoWithGemini = (id: string) =>
  apiFetch<AIExplanation>(`/api/repos/${id}/ai-explain`, {
    method: "POST",
  });

export const toggleRepo = (id: string, is_active: boolean) =>
  apiFetch<{ id: string; is_active: boolean }>(`/api/repos/${id}/toggle`, {
    method: "POST",
    body: JSON.stringify({ is_active }),
  });

export const updateRepoSettings = (
  id: string,
  settings: { requires_tests?: boolean; requires_typecheck?: boolean; is_active?: boolean }
) =>
  apiFetch<{ id: string; full_name: string; requires_tests: boolean; requires_typecheck: boolean; is_active: boolean }>(
    `/api/repos/${id}`,
    {
      method: "PATCH",
      body: JSON.stringify(settings),
    }
  );

// ── Activity ───────────────────────────────────────────────────────────────

export interface ActivityItem {
  id: string;
  type: "pull_request" | "patch" | "detected_change";
  repo_name: string;
  title: string;
  description: string;
  status: string;
  url?: string | null;
  timestamp?: string | null;
  merged?: boolean;
  verification_mode?: string | null;
}

export const getActivity = () => apiFetch<{ activities: ActivityItem[] }>("/api/activity");

// ── Patches ────────────────────────────────────────────────────────────────

export interface PatchSummary {
  id: string;
  package: string;
  old_version: string;
  new_version: string;
  status: "open" | "merged" | "closed" | "pending" | "patched" | "failed" | "verified" | "generated";
  pr_url?: string;
  usages_patched: number;
  opened_at: string;
  diff?: string | null;
  verification_mode?: string | null;
  tests_passed?: boolean | null;
  typecheck_passed?: boolean | null;
  change_type?: string | null;
  change_description?: string | null;
}

export interface RepoPatches {
  repo: string;
  patches: PatchSummary[];
}

export const getRepoPatches = (repoId: string) =>
  apiFetch<RepoPatches>(`/api/repos/${repoId}/patches`);

// ── Recovery (Engine B) ────────────────────────────────────────────────────

export interface RecoveryStats {
  total_payment_attempts: number;
  total_recovery_events: number;
  recovered: number;
  escalated: number;
  unresolved: number;
  payment_recovery_rate?: number;
  recovery_execution_rate?: number;
  recovery_rate?: number;
  tier1_classified: number;
  tier2_classified: number;
  revenue_at_risk: number;      // paise
  revenue_recovered: number;    // paise
}

export interface RecoveryEvent {
  id: string;
  payment_attempt_id: string;
  failure_type: string;
  classification: "transient" | "code_defect" | "unknown";
  action_taken: string;
  action?: string;
  stage?: string;
  llm_provider: string;
  llm_model: string;
  outcome: "recovered" | "escalated" | "unresolved" | "pending";
  pull_request_id?: string | null;
  amount?: number;
  retry_count?: number;
  detected_at: string;
  resolved_at?: string | null;
}

export const getRecoveryStats = () =>
  apiFetch<RecoveryStats>("/api/recovery/stats");

export const getRecoveryEvents = (limit = 20, offset = 0) =>
  apiFetch<RecoveryEvent[]>(`/api/recovery/events?limit=${limit}&offset=${offset}`);

export interface BatchRunParams {
  count: number;
  failure_rate: number;
  client_request_id?: string;
}

export interface BatchRunResult {
  status: string;
  payment_attempt_ids: string[];
}

export const triggerBatchRun = (params: BatchRunParams) =>
  apiFetch<BatchRunResult>("/api/payments/batch-run", {
    method: "POST",
    body: JSON.stringify({
      ...params,
      client_request_id: params.client_request_id ?? `demo-${Date.now()}`,
    }),
  });
