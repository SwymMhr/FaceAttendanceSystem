// src/api.js
// Central place for API calls + auth/localStorage helpers.

import axios from "axios";

const API_BASE_URL = "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
});

// Attach the stored token to every request automatically, if present.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Auth ───────────────────────────────────────────────────────────────────

export async function loginUser(username, password) {
  const res = await api.post("/login", { username, password });
  const { access_token, username: returnedUsername, role } = res.data;

  localStorage.setItem("token", access_token);
  localStorage.setItem("username", returnedUsername);
  localStorage.setItem("role", role);

  return res.data;
}

export function logoutUser() {
  localStorage.removeItem("token");
  localStorage.removeItem("username");
  localStorage.removeItem("role");
}

export function isLoggedIn() {
  return Boolean(localStorage.getItem("token"));
}

export function getRole() {
  return localStorage.getItem("role");
}

// ── Dashboards ─────────────────────────────────────────────────────────────

export async function getStudentSummary() {
  const res = await api.get("/student/me/summary");
  return res.data;
}

export async function getStudentTrend(days = 30) {
  const res = await api.get(`/student/me/trend?days=${days}`);
  return res.data;
}

export async function getStudentHistory(limit = 100) {
  const res = await api.get(`/student/me/history?limit=${limit}`);
  return res.data;
}

export async function getTeacherToday() {
  const res = await api.get("/teacher/me/today");
  return res.data;
}

export async function getTeacherBatches() {
  const res = await api.get("/teacher/me/batches");
  return res.data;
}

export async function getBatchRoster(batchId, params = {}) {
  const query = new URLSearchParams(params).toString();
  const res = await api.get(`/teacher/batch/${batchId}/roster${query ? `?${query}` : ""}`);
  return res.data;
}

export async function getBatchTrend(batchId, days = 30) {
  const res = await api.get(`/teacher/batch/${batchId}/trend?days=${days}`);
  return res.data;
}

export async function getAdminOverview() {
  const res = await api.get("/admin/overview");
  return res.data;
}

export default api;