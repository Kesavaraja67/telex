/** Organism View — shared TypeScript types */

export interface IncidentNode {
  code_usage_id: string;
  file_path: string;
  line_start: number;
  line_end: number;
  status: "pending" | "patched" | "skipped" | "failed" | string;
  patch_verified?: boolean | null;
  validation?: {
    applies_cleanly: boolean;
    typechecks: boolean | null;
    tests_pass: boolean | null;
    scope_ok: boolean;
    verification_mode?: string;
  } | null;
  pr_url?: string | null;
  pr_merged?: boolean | null;
}

export interface IncidentGraph {
  detected_change_id: string;
  repo_id: string;
  package: string;
  symbol_old: string;
  symbol_new?: string | null;
  change_type: string;
  confidence: number;
  created_at: string;
  nodes: IncidentNode[];
}

export interface IncidentEvent {
  event_type: string;
  repo_id?: string | null;
  detected_change_id?: string | null;
  code_usage_id?: string | null;
  job_id?: string | null;
  payload?: Record<string, unknown>;
}

/**
 * Data source interface — decouples OrganismView from the transport layer.
 * Dashboard uses DashboardDataSource (real SSE + REST).
 * Marketing uses FixtureDataSource (looping synthetic scenario).
 * Replay uses ReplayDataSource (historical event playback).
 */
export interface OrganismDataSource {
  /** Return a full current-state snapshot for the given incident. */
  fetchSnapshot(): Promise<IncidentGraph>;
  /**
   * Subscribe to live events. Returns an unsubscribe function.
   * Must call onEvent for each new event from the data source.
   */
  subscribe(onEvent: (e: IncidentEvent) => void): () => void;
}
