import { API_BASE } from "@/lib/api";

export interface LastEditedEntry {
  status: "idle" | "loading" | "done" | "error";
  value?: string;
  rawDate?: string;
  author?: string;
}

const cache = new Map<string, LastEditedEntry>();
const listeners = new Map<string, Set<(entry: LastEditedEntry) => void>>();

// Queue for debounced batch fetching
const pendingQueue = new Map<string, { repoId: string; filePath: string; ref: string }>();
let debounceTimer: ReturnType<typeof setTimeout> | null = null;

function formatRelativeTime(isoString?: string): string {
  if (!isoString) return "";
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffDays > 30) {
      return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    }
    if (diffDays > 0) return `${diffDays}d ago`;
    if (diffHours > 0) return `${diffHours}h ago`;
    if (diffMins > 0) return `${diffMins}m ago`;
    return "just now";
  } catch {
    return "";
  }
}

async function processQueue() {
  const currentBatch = Array.from(pendingQueue.entries());
  pendingQueue.clear();
  debounceTimer = null;

  for (const [key, { repoId, filePath, ref }] of currentBatch) {
    try {
      const params = new URLSearchParams({ path: filePath, ref });
      const headers: Record<string, string> = {};
      if (typeof window !== "undefined") {
        const token = localStorage.getItem("telex_token");
        if (token) headers["Authorization"] = `Bearer ${token}`;
      }
      const res = await fetch(
        `${API_BASE}/api/repos/${repoId}/atlas/last-edited?${params}`,
        { credentials: "include", headers }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const lastCommit = data.last_edited;
      const formatted = lastCommit?.committed_at
        ? formatRelativeTime(lastCommit.committed_at)
        : "";

      const entry: LastEditedEntry = {
        status: "done",
        value: formatted,
        rawDate: lastCommit?.committed_at,
        author: lastCommit?.author,
      };
      cache.set(key, entry);
      notify(key, entry);
    } catch {
      const entry: LastEditedEntry = { status: "error" };
      cache.set(key, entry);
      notify(key, entry);
    }
  }
}

function notify(key: string, entry: LastEditedEntry) {
  const cbs = listeners.get(key);
  if (cbs) {
    cbs.forEach((cb) => cb(entry));
  }
}

export function getLastEdited(key: string): LastEditedEntry | undefined {
  return cache.get(key);
}

export function subscribeLastEdited(
  repoId: string,
  filePath: string,
  ref: string,
  callback: (entry: LastEditedEntry) => void
): () => void {
  const key = `${repoId}:${ref}:${filePath}`;
  if (!listeners.has(key)) {
    listeners.set(key, new Set());
  }
  listeners.get(key)!.add(callback);

  const existing = cache.get(key);
  if (existing) {
    callback(existing);
    if (existing.status === "done" || existing.status === "error") {
      return () => {
        listeners.get(key)?.delete(callback);
      };
    }
  }

  if (!existing || existing.status === "idle") {
    cache.set(key, { status: "loading" });
    pendingQueue.set(key, { repoId, filePath, ref });
    if (!debounceTimer) {
      debounceTimer = setTimeout(processQueue, 150);
    }
  }

  return () => {
    listeners.get(key)?.delete(callback);
  };
}
