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
};
