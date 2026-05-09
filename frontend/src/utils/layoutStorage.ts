/**
 * Persist and restore the expanded blueprint/route state in GraphCanvas across page reloads.
 * Key is derived from the scan timestamp so stale state is ignored after a rescan.
 */

const LS_KEY_PREFIX = 'flask-brain:expansion:';

export interface PersistedExpansion {
  blueprints: string[];
  routes: string[];
  viewport?: { x: number; y: number; zoom: number };
}

export function loadExpansion(scanTimestamp: string): PersistedExpansion | null {
  try {
    const raw = localStorage.getItem(LS_KEY_PREFIX + scanTimestamp);
    if (!raw) return null;
    return JSON.parse(raw) as PersistedExpansion;
  } catch {
    return null;
  }
}

export function saveExpansion(scanTimestamp: string, data: PersistedExpansion): void {
  try {
    localStorage.setItem(LS_KEY_PREFIX + scanTimestamp, JSON.stringify(data));
    // Prune old entries (keep only 10 most recent)
    const keys = Object.keys(localStorage).filter(k => k.startsWith(LS_KEY_PREFIX));
    if (keys.length > 10) {
      keys.sort(); // lexicographic — ISO timestamps sort chronologically
      const toRemove = keys.slice(0, keys.length - 10);
      toRemove.forEach(k => localStorage.removeItem(k));
    }
  } catch {
    // localStorage may be unavailable (private mode, quota exceeded) — silently ignore
  }
}

export function clearExpansion(scanTimestamp: string): void {
  try {
    localStorage.removeItem(LS_KEY_PREFIX + scanTimestamp);
  } catch {
    // ignore
  }
}
