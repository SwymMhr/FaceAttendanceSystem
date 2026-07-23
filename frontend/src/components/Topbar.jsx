import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import "./Topbar.css";

// Maps the current route to a human title for the breadcrumb in the middle
// of the bar — mirrors the reference screenshot's "2:16:03 PM · Customer
// Support". Checked longest-prefix-first so child routes (e.g. a batch
// roster page) still resolve sensibly.
const PAGE_TITLES = [
  ["/student/history", "History"],
  ["/student", "My Attendance"],
  ["/teacher/enroll", "Register Faces"],
  ["/teacher/attendance", "Live Attendance"],
  ["/teacher/history", "History"],
  ["/teacher/batch", "Batch Roster"],
  ["/teacher", "Dashboard"],
  ["/admin/batches", "Batches"],
  ["/admin/subjects", "Subjects"],
  ["/admin/users", "Users"],
  ["/admin/schedule", "Schedule"],
  ["/admin", "Overview"],
];

function getPageTitle(pathname) {
  const match = PAGE_TITLES.find(([prefix]) => pathname.startsWith(prefix));
  return match ? match[1] : "";
}

export default function Topbar({ displayName, onToggleSidebar }) {
  const location = useLocation();
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const initial = (displayName || "?").charAt(0).toUpperCase();
  const pageTitle = getPageTitle(location.pathname);
  const timeString = now.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  });

  return (
    <header className="app-topbar">
      <div className="app-topbar__left">
        <button
          className="app-topbar__hamburger d-lg-none"
          onClick={onToggleSidebar}
          aria-label="Toggle menu"
        >
          <i className="bi bi-list" />
        </button>
        <span className="app-topbar__clock">{timeString}</span>
        {pageTitle && (
          <>
            <span className="app-topbar__divider">·</span>
            <span className="app-topbar__page">{pageTitle}</span>
          </>
        )}
      </div>

      <div className="app-topbar__right">
        <div className="app-topbar__avatar" title={displayName}>
          {initial}
        </div>
      </div>
    </header>
  );
}