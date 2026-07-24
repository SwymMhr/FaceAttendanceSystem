import { useState } from "react";
import { Routes, Route, Navigate, useNavigate } from "react-router-dom";
import RegisterFacePage from "./pages/RegisterFacePage";
import AttendancePage from "./pages/AttendancePage";
import HistoryPage from "./pages/HistoryPage";
import LoginPage from "./pages/LoginPage";
import StudentDashboard from "./pages/StudentDashboard";
import StudentHistory from "./pages/StudentHistory";
import TeacherDashboard from "./pages/TeacherDashboard";
import BatchRosterPage from "./pages/BatchRosterPage";
import PeriodAttendancePage from "./pages/PeriodAttendancePage";
import AdminDashboard from "./pages/AdminDashboard";
import AdminBatches from "./pages/AdminBatches";
import AdminSubjects from "./pages/AdminSubjects";
import AdminUsers from "./pages/AdminUsers";
import AddStudentPage from "./pages/AddStudentPage";
import AddTeacherPage from "./pages/AddTeacherPage";
import EditUserPage from "./pages/EditUserPage";
import AdminSchedule from "./pages/AdminSchedule";
import AddPeriodSlotPage from "./pages/AddPeriodSlotPage";
import ProtectedRoute from "./components/ProtectedRoute";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import { isLoggedIn, logoutUser, getRole } from "./api";
import "./App.css";

// "/" doesn't render a page itself — it just sends each logged-in user
// to whichever dashboard actually belongs to their role.
function HomeRedirect() {
  const role = getRole();
  if (role === "admin") return <Navigate to="/admin" replace />;
  if (role === "teacher") return <Navigate to="/teacher" replace />;
  if (role === "student") return <Navigate to="/student" replace />;
  return <Navigate to="/login" replace />;
}

export default function App() {
  const navigate = useNavigate();
  const loggedIn = isLoggedIn();
  const displayName = localStorage.getItem("displayName");
  const role = getRole();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = () => {
    logoutUser();
    navigate("/login");
  };

  const closeSidebar = () => setSidebarOpen(false);

  return (
    <>
      {/* Topbar + Sidebar only render once logged in. Sidebar's link set is
          role-driven internally (see components/Sidebar.jsx) — no Register
          link either way, since accounts are admin-created. */}
      {loggedIn && (
        <>
          <Topbar displayName={displayName} onToggleSidebar={() => setSidebarOpen((v) => !v)} />
          <Sidebar
            role={role}
            displayName={displayName}
            open={sidebarOpen}
            onNavigate={closeSidebar}
            onLogout={handleLogout}
          />
        </>
      )}

      <div className={loggedIn ? "app-content" : undefined}>
      <Routes>
        {/* Public route. If already logged in, skip straight past it. */}
        <Route
          path="/login"
          element={loggedIn ? <Navigate to="/" replace /> : <LoginPage />}
        />

        {/* "/" redirects to the right dashboard for whoever's logged in */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <HomeRedirect />
            </ProtectedRoute>
          }
        />

        {/* Student */}
        <Route
          path="/student"
          element={
            <ProtectedRoute roles={["student"]}>
              <StudentDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/student/history"
          element={
            <ProtectedRoute roles={["student"]}>
              <StudentHistory />
            </ProtectedRoute>
          }
        />

        {/* Teacher (admin can also reach these — e.g. to run enrollment/live capture) */}
        <Route
          path="/teacher"
          element={
            <ProtectedRoute roles={["teacher"]}>
              <TeacherDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/teacher/enroll"
          element={
            <ProtectedRoute roles={["admin"]}>
              <RegisterFacePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/teacher/attendance"
          element={
            <ProtectedRoute roles={["teacher", "admin"]}>
              <AttendancePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/teacher/history"
          element={
            <ProtectedRoute roles={["teacher", "admin"]}>
              <HistoryPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/teacher/batch/:batchId"
          element={
            <ProtectedRoute roles={["teacher", "admin"]}>
              <BatchRosterPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/teacher/period/:periodId"
          element={
            <ProtectedRoute roles={["teacher", "admin"]}>
              <PeriodAttendancePage />
            </ProtectedRoute>
          }
        />

        {/* Admin */}
        <Route
          path="/admin"
          element={
            <ProtectedRoute roles={["admin"]}>
              <AdminDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/batches"
          element={
            <ProtectedRoute roles={["admin"]}>
              <AdminBatches />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/subjects"
          element={
            <ProtectedRoute roles={["admin"]}>
              <AdminSubjects />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/users"
          element={
            <ProtectedRoute roles={["admin"]}>
              <AdminUsers />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/users/new-student"
          element={
            <ProtectedRoute roles={["admin"]}>
              <AddStudentPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/users/new-teacher"
          element={
            <ProtectedRoute roles={["admin"]}>
              <AddTeacherPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/users/:userId/edit"
          element={
            <ProtectedRoute roles={["admin"]}>
              <EditUserPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/schedule"
          element={
            <ProtectedRoute roles={["admin"]}>
              <AdminSchedule />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/schedule/add-period"
          element={
            <ProtectedRoute roles={["admin"]}>
              <AddPeriodSlotPage />
            </ProtectedRoute>
          }
        />

        {/* Anything else falls back to the login gate (ProtectedRoute/HomeRedirect
            will bounce logged-in users to their real dashboard from there). */}
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
      </div>
    </>
  );
}