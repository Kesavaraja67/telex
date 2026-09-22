import { API_BASE } from "@/lib/api";
import type { IncidentEvent, IncidentGraph, OrganismDataSource } from "./types";

/**
 * Real-data source for the dashboard incident view.
 * - fetchSnapshot(): REST call → /api/repos/{repoId}/incidents/{changeId}/graph
 * - subscribe(): EventSource SSE → /api/repos/{repoId}/incidents/stream
 *
 * withCredentials:true means the browser sends the httpOnly telex_session
 * cookie automatically — no token in the URL.
 */
export class DashboardDataSource implements OrganismDataSource {
  private repoId: string;
  private changeId: string;

  constructor(repoId: string, changeId: string) {
    this.repoId = repoId;
    this.changeId = changeId;
  }

  async fetchSnapshot(): Promise<IncidentGraph> {
    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("telex_token")
        : null;
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(
      `${API_BASE}/api/repos/${this.repoId}/incidents/${this.changeId}/graph`,
      { credentials: "include", headers }
    );
    if (!res.ok) throw new Error(`snapshot fetch failed: ${res.status}`);
    return res.json() as Promise<IncidentGraph>;
  }

  subscribe(onEvent: (e: IncidentEvent) => void): () => void {
    const url = `${API_BASE}/api/repos/${this.repoId}/incidents/stream`;
    const es = new EventSource(url, { withCredentials: true });

    es.onmessage = (ev) => {
      try {
        const event = JSON.parse(ev.data) as IncidentEvent;
        // Filter to events relevant to this incident
        if (
          !event.detected_change_id ||
          event.detected_change_id === this.changeId
        ) {
          onEvent(event);
        }
      } catch {
        // malformed SSE frame — ignore
      }
    };

    es.onerror = () => {
      // EventSource auto-reconnects; nothing to do
    };

    return () => es.close();
  }
}
