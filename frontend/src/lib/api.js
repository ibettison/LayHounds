import axios from "axios";

// Normalise REACT_APP_BACKEND_URL so misconfigurations (trailing slash, missing scheme,
// dev host with no port) produce a clear error rather than a cryptic "Failed to construct URL".
function resolveBackendUrl() {
  let raw = (process.env.REACT_APP_BACKEND_URL || "").trim();
  if (!raw) {
    // Fall back to current origin so the SPA still works when env wasn't baked at build time.
    if (typeof window !== "undefined" && window.location?.origin) {
      console.warn("[api] REACT_APP_BACKEND_URL was empty at build time — falling back to window.location.origin");
      return window.location.origin;
    }
    throw new Error("REACT_APP_BACKEND_URL is not set");
  }
  raw = raw.replace(/\/+$/, ""); // strip trailing slashes
  if (!/^https?:\/\//i.test(raw)) {
    // Auto-prefix protocol so "lay-hounds.co.uk" works
    raw = `https://${raw}`;
  }
  try {
    // Validate — throws on malformed URL
    // eslint-disable-next-line no-new
    new URL(raw);
  } catch (e) {
    throw new Error(`REACT_APP_BACKEND_URL is invalid: ${raw} (${e.message})`);
  }
  return raw;
}

const BACKEND_URL = resolveBackendUrl();
export const API = `${BACKEND_URL}/api`;

export const api = {
  createSession: (config) => axios.post(`${API}/sessions`, config).then((r) => r.data),
  listSessions: () => axios.get(`${API}/sessions`).then((r) => r.data),
  getSession: (id) => axios.get(`${API}/sessions/${id}`).then((r) => r.data),
  nextRace: (id) => axios.post(`${API}/sessions/${id}/next-race`).then((r) => r.data),
  stopSession: (id) => axios.post(`${API}/sessions/${id}/stop`).then((r) => r.data),
  deleteSession: (id) => axios.delete(`${API}/sessions/${id}`).then((r) => r.data),
  betfairStatus: () => axios.get(`${API}/betfair/status`).then((r) => r.data),
  currentBank: () => axios.get(`${API}/bank/current`).then((r) => r.data),
  dailyStats: () => axios.get(`${API}/daily-stats`).then((r) => r.data),
  previewCap: (params) => axios.post(`${API}/preview-cap`, params).then((r) => r.data),
  runRaces: (id, count) => axios.post(`${API}/sessions/${id}/run-races?count=${count}`).then((r) => r.data),
  resetAll: () => axios.delete(`${API}/sessions`).then((r) => r.data),
  startCheckout: (provider) => axios.post(`${API}/payments/${provider}/checkout`).then((r) => r.data),
  contact: (payload) => axios.post(`${API}/contact`, payload).then((r) => r.data),
  betfairFunds: () => axios.get(`${API}/betfair/funds`).then((r) => r.data),
  betfairRaces: (minutesAhead = 60) => axios.get(`${API}/betfair/races?minutes_ahead=${minutesAhead}`).then((r) => r.data),
  refreshBank: (id) => axios.post(`${API}/sessions/${id}/refresh-bank`).then((r) => r.data),
  refreshLiveSettlement: (id) => axios.post(`${API}/sessions/${id}/refresh-live-settlement`).then((r) => r.data),
};
