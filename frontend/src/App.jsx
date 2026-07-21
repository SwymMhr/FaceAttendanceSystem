import { Routes, Route, Navigate, NavLink, useNavigate } from "react-router-dom";
import EnrollPage from "./pages/EnrollPage";
import AttendancePage from "./pages/AttendancePage";
import HistoryPage from "./pages/HistoryPage";
import LoginPage from "./pages/LoginPage";
import ProtectedRoute from "./components/ProtectedRoute";
import { isLoggedIn, logoutUser } from "./api";

export default function App() {
  const navigate = useNavigate();
  const loggedIn = isLoggedIn();
  const username = localStorage.getItem("username");

  const handleLogout = () => {
    logoutUser();
    navigate("/login");
  };

  return (
    <>
      {/* Navbar only renders once the user is authenticated.
          Login/Register are entry points, not app sections, so they're
          intentionally left out of it. */}
      {loggedIn && (
        <nav className="navbar navbar-expand-lg navbar-dark bg-dark">
          <div className="container">
            <div className="navbar-nav ms-auto align-items-lg-center">
              <NavLink className="nav-link" to="/"> Enroll </NavLink>
              <NavLink className="nav-link" to="/attendance"> Live Attendance </NavLink>
              <NavLink className="nav-link" to="/history"> History </NavLink>

              <span className="nav-link text-white-50">Hi, {username}</span>
              <button className="btn btn-outline-light btn-sm ms-lg-2" onClick={handleLogout}>
                Logout
              </button>
            </div>
          </div>
        </nav>
      )}

      <Routes>
        {/* Public routes. If someone is already logged in and lands on
            /login or /register, send them straight into the app instead. */}
        <Route
          path="/login"
          element={loggedIn ? <Navigate to="/" replace /> : <LoginPage />}
        />

        {/* Protected app pages — each redirects to /login if not authenticated. */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <EnrollPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/attendance"
          element={
            <ProtectedRoute>
              <AttendancePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/history"
          element={
            <ProtectedRoute>
              <HistoryPage />
            </ProtectedRoute>
          }
        />

        {/* Anything else falls back to the login gate. */}
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </>
  );
}
