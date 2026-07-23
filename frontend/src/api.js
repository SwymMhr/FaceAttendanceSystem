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

export async function loginUser(email, password) {
  const res = await api.post("/login", { email, password });
  const { access_token, display_name, role } = res.data;

  localStorage.setItem("token", access_token);
  localStorage.setItem("displayName", display_name);
  localStorage.setItem("role", role);

  return res.data;
}

export function logoutUser() {
  localStorage.removeItem("token");
  localStorage.removeItem("displayName");
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

// ── Period attendance review + manual override ──────────────────────────────
// Lists every student in a period's batch with their current status
// ("pending" = camera-detected, awaiting confirmation; "present"/"absent" =
// confirmed; "none" = no record yet) and lets a teacher confirm, reject, or
// force-mark any of them regardless of what the camera saw.

export async function getPeriodAttendance(periodId, date) {
  const query = date ? `?date=${date}` : "";
  const res = await api.get(`/teacher/period/${periodId}/attendance${query}`);
  return res.data;
}

export async function setPeriodAttendance(periodId, studentId, status, date) {
  const query = date ? `?date=${date}` : "";
  const res = await api.post(`/teacher/period/${periodId}/attendance${query}`, {
    student_id: studentId,
    status,
  });
  return res.data;
}

export async function finalizePeriod(periodId, targetDate) {
  // POST /finalize_period — manual trigger for the same absence-backfill +
  // email job the background scheduler runs automatically once a period
  // ends. period_id/target_date are plain query params on this route, not
  // a JSON body.
  const params = new URLSearchParams({ period_id: periodId });
  if (targetDate) params.append("target_date", targetDate);
  const res = await api.post(`/finalize_period?${params.toString()}`);
  return res.data;
}

export async function getAdminOverview() {
  const res = await api.get("/admin/overview");
  return res.data;
}

// ── Attendance logs (teacher/admin "History" page) ─────────────────────────

export async function getAttendanceLogs(filters = {}) {
  const params = {};
  if (filters.startDate) params.start_date = filters.startDate;
  if (filters.endDate) params.end_date = filters.endDate;
  if (filters.studentName) params.student_name = filters.studentName;
  if (filters.batchId) params.batch_id = filters.batchId;
  if (filters.teacherId) params.teacher_id = filters.teacherId;
  params.limit = filters.limit || 100;

  const res = await api.get("/get_attendance_logs", { params });
  return res.data;
}

export async function getAttendanceFilterOptions() {
  const res = await api.get("/attendance_filters");
  return res.data;
}

// ── Admin: Batches ───────────────────────────────────────────────────────────

export async function getBatches() {
  const res = await api.get("/admin/batches");
  return res.data;
}

export async function createBatch(batch_name) {
  const res = await api.post("/admin/batches", { batch_name });
  return res.data;
}

export async function updateBatch(batchId, batch_name) {
  const res = await api.put(`/admin/batches/${batchId}`, { batch_name });
  return res.data;
}

export async function deleteBatch(batchId) {
  const res = await api.delete(`/admin/batches/${batchId}`);
  return res.data;
}

// ── Admin: Subjects ──────────────────────────────────────────────────────────

export async function getSubjects() {
  const res = await api.get("/admin/subjects");
  return res.data;
}

export async function createSubject(subject_code, subject_name) {
  const res = await api.post("/admin/subjects", { subject_code, subject_name });
  return res.data;
}

export async function updateSubject(subjectId, subject_code, subject_name) {
  const res = await api.put(`/admin/subjects/${subjectId}`, { subject_code, subject_name });
  return res.data;
}

export async function deleteSubject(subjectId) {
  const res = await api.delete(`/admin/subjects/${subjectId}`);
  return res.data;
}

// ── Admin: Users (teachers + students) ───────────────────────────────────────

export async function getUsers(role) {
  const query = role ? `?role=${role}` : "";
  const res = await api.get(`/admin/users${query}`);
  return res.data;
}

export async function getUser(userId) {
  const res = await api.get(`/admin/users/${userId}`);
  return res.data;
}

export async function createTeacher(payload) {
  // payload: { full_name, email, password }
  const res = await api.post("/admin/users/teachers", payload);
  return res.data;
}

export async function createStudent(payload) {
  // payload: { email, password, student_code, student_name, batch_id }
  const res = await api.post("/admin/users/students", payload);
  return res.data;
}

export async function updateUser(userId, payload) {
  // payload: { email?, password?, is_active?, role?, full_name?, student_code?, student_name?, batch_id? }
  const res = await api.put(`/admin/users/${userId}`, payload);
  return res.data;
}

export async function deleteUser(userId) {
  const res = await api.delete(`/admin/users/${userId}`);
  return res.data;
}

// ── Face registration (attach photos to an EXISTING student) ────────────────
// Students themselves are created by an admin via createStudent() above —
// this is only for adding face photos to a student who already exists.

export async function getBatchStudents(batchId) {
  // No batch-scoped student-list endpoint on the backend yet, so fetch all
  // students and filter client-side. Fine at school-roster scale.
  const students = await getUsers("student");
  return batchId ? students.filter((s) => s.batch_id === Number(batchId)) : students;
}

export async function getEmbeddingCount(studentId) {
  const res = await api.get(`/students/${studentId}/embeddings`);
  return res.data;
}

export async function registerFace(studentId, images) {
  const formData = new FormData();
  formData.append("student_id", studentId);
  for (const img of images) {
    formData.append("images", img);
  }
  const res = await api.post("/register_face", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

// ── Admin: Schedule (period slots + periods/timetable) ───────────────────────

export async function getPeriodSlots() {
  const res = await api.get("/admin/period-slots");
  return res.data;
}

export async function getPeriods(params = {}) {
  const query = new URLSearchParams(params).toString();
  const res = await api.get(`/admin/periods${query ? `?${query}` : ""}`);
  return res.data;
}

export async function getBatchTimetable(batchId) {
  const res = await api.get(`/admin/periods/timetable/${batchId}`);
  return res.data;
}

export async function createPeriod(payload) {
  // payload: { batch_id, subject_id, teacher_id, day_of_week, period_number }
  const res = await api.post("/admin/periods", payload);
  return res.data;
}

export async function updatePeriod(periodId, payload) {
  const res = await api.put(`/admin/periods/${periodId}`, payload);
  return res.data;
}

export async function deletePeriod(periodId) {
  const res = await api.delete(`/admin/periods/${periodId}`);
  return res.data;
}

export default api;