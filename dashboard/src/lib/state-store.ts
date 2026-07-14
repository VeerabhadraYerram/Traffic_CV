/**
 * state-store.ts
 *
 * Central data service for the VigilantEye dashboard.
 * All hooks import `dataService`, `USE_MOCK_DATA`, and `globalStateStore` from here.
 *
 * In production (Docker / on-premise), USE_MOCK_DATA is false and dataService
 * calls the FastAPI backend directly. The globalStateStore is a no-op stub that
 * satisfies hook imports without doing anything.
 */

import type { ConfiguratorCamera, NormalizedLine, VehicleEvent, Violation } from '@/types';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

/** Set to true only during UI development without a running backend. */
export const USE_MOCK_DATA = false;

// ---------------------------------------------------------------------------
// Minimal event emitter (stub — only used when USE_MOCK_DATA is true)
// ---------------------------------------------------------------------------

type Listener = () => void;

class EventEmitter {
  private listeners: Set<Listener> = new Set();

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  emit() {
    this.listeners.forEach((l) => l());
  }
}

export const globalStateStore = new EventEmitter();

// ---------------------------------------------------------------------------
// API base — empty string means same origin (works in both Docker and dev proxy)
// ---------------------------------------------------------------------------

const API_BASE = '';

// ---------------------------------------------------------------------------
// Data Service
// ---------------------------------------------------------------------------

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`API error ${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const dataService = {
  /** Returns all active cameras with both configurator and dashboard fields. */
  getCameras: () =>
    apiFetch<ConfiguratorCamera[]>('/api/cameras'),

  /** Returns last 100 vehicle access events joined with camera name. */
  getEvents: () =>
    apiFetch<VehicleEvent[]>('/api/events'),

  /** Returns last 100 violations ordered by created_at desc. */
  getViolations: () =>
    apiFetch<Violation[]>('/api/violations'),

  /** Updates a violation's status field (ACKNOWLEDGED, RESOLVED, etc.). */
  acknowledgeViolation: (violationId: string, status: string) =>
    apiFetch<{ status: string; message: string }>(
      `/api/violations/${violationId}/acknowledge`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      }
    ),

  /** Saves normalized entry/exit line coords for a camera. */
  saveCameraLines: (
    cameraId: string,
    payload: {
      entry_line?: NormalizedLine | null;
      exit_line?: NormalizedLine | null;
    }
  ) =>
    apiFetch<{ status: string; message: string }>(
      `/api/cameras/${cameraId}/lines`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }
    ),
};
