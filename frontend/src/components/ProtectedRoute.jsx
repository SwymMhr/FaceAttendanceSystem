import { Navigate } from "react-router-dom";
import { isLoggedIn, getRole } from "../api";

/**
 * Wrap any page that should only be reachable while logged in.
 * Optionally pass roles={['admin']} (or any list) to also gate by role —
 * if the logged-in user's role isn't in the list, they're redirected to
 * their own dashboard instead of seeing a page that isn't theirs.
 *
 * <ProtectedRoute><EnrollPage /></ProtectedRoute>                — any logged-in user
 * <ProtectedRoute roles={['admin']}><AdminUsers /></ProtectedRoute> — admin only
 */
export default function ProtectedRoute({ children, roles }) {
  if (!isLoggedIn()) {
    return <Navigate to="/login" replace />;
  }

  const role = getRole();

  if (roles && !roles.includes(role)) {
    // Logged in, but wrong role for this page — send them home,
    // where "/" itself redirects to whichever dashboard is actually theirs.
    return <Navigate to="/" replace />;
  }

  return children;
}