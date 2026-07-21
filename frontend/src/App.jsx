import { Routes, Route, Navigate, NavLink, useNavigate } from "react-router-dom";
import EnrollPage from "./pages/EnrollPage";
import AttendancePage from "./pages/AttendancePage";
import HistoryPage from "./pages/HistoryPage";
import LoginPage from "./pages/LoginPage";
import StudentDashboard from "./pages/StudentDashboard";
import TeacherDashboard from "./pages/TeacherDashboard";
import BatchRosterPage from "./pages/BatchRosterPage";
import AdminDashboard from "./pages/AdminDashboard";
import ProtectedRoute from "./components/ProtectedRoute";
import { isLoggedIn, logoutUser, getRole } from "./api";

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
  const username = localStorage.getItem("username");
  const role = getRole();

  const handleLogout = () => {
    logoutUser();
    navigate("/login");
  };

  return (
    <>
      {/* Navbar only renders once logged in, and only shows links relevant
          to that user's role. No Register link — accounts are admin-created. */}
      {loggedIn && (
        <nav className="navbar navbar-expand-lg navbar-dark bg-dark">
          <div className="container">
            <div className="navbar-nav ms-auto align-items-lg-center">
              {role === "student" && (
                <NavLink className="nav-link" to="/student">My Attendance</NavLink>
              )}

              {role === "teacher" && (
                <>
                  <NavLink className="nav-link" to="/teacher">Dashboard</NavLink>
                  <NavLink className="nav-link" to="/teacher/enroll">Enroll</NavLink>
                  <NavLink className="nav-link" to="/teacher/attendance">Live Attendance</NavLink>
                  <NavLink className="nav-link" to="/teacher/history">History</NavLink>
                </>
              )}

              {role === "admin" && (
                <>
                  <NavLink className="nav-link" to="/admin">Overview</NavLink>
                  <NavLink className="nav-link" to="/teacher/enroll">Enroll</NavLink>
                  <NavLink className="nav-link" to="/teacher/attendance">Live Attendance</NavLink>
                  <NavLink className="nav-link" to="/teacher/history">History</NavLink>
                </>
              )}

              <span className="nav-link text-white-50">Hi, {username}</span>
              <button className="btn btn-outline-light btn-sm ms-lg-2" onClick={handleLogout}>
                Logout
              </button>
            </div>
          </div>
        </nav>
      )}

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
            <ProtectedRoute roles={["teacher", "admin"]}>
              <EnrollPage />
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

        {/* Admin */}
        <Route
          path="/admin"
          element={
            <ProtectedRoute roles={["admin"]}>
              <AdminDashboard />
            </ProtectedRoute>
          }
        />

        {/* Anything else falls back to the login gate (ProtectedRoute/HomeRedirect
            will bounce logged-in users to their real dashboard from there). */}
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </>
  );
}