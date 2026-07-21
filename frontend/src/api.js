import axios from "axios";

const API = axios.create({
  baseURL: "http://127.0.0.1:8000",
});

// Attach the saved JWT (if any) to every outgoing request.
API.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const getAttendanceLogs = () =>
  API.get("/get_attendance_logs");

// ── Auth ─────────────────────────────────────────────────────────────────────

export const loginUser = (username, password) =>
  API.post("/login", { username, password });

export const logoutUser = () => {
  localStorage.removeItem("access_token");
  localStorage.removeItem("username");
};

export const isLoggedIn = () => !!localStorage.getItem("access_token");

export default API;