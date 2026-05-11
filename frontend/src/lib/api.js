import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
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
  refreshBank: (id) => axios.post(`${API}/sessions/${id}/refresh-bank`).then((r) => r.data),
};
