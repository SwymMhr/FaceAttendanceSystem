import { useEffect } from "react";
import { NavLink } from "react-router-dom";
import "./Sidebar.css";

// Same routes App.jsx already defines per role — just re-expressed here as
// data so the sidebar can render them as an icon list instead of a plain
// navbar. Paths that are a role's "home" route use `end` so they don't stay
// highlighted while on a deeper child route.
const NAV_BY_ROLE = {
  student: [
    { label: "My Attendance", path: "/student", icon: "bi-speedometer2", end: true },
    { label: "History", path: "/student/history", icon: "bi-clock-history" },
  ],
  teacher: [
    { label: "Dashboard", path: "/teacher", icon: "bi-speedometer2", end: true },
    { label: "Register Faces", path: "/teacher/enroll", icon: "bi-camera" },
    { label: "Live Attendance", path: "/teacher/attendance", icon: "bi-person-video2" },
    { label: "History", path: "/teacher/history", icon: "bi-clock-history" },
  ],
  admin: [
    { label: "Overview", path: "/admin", icon: "bi-speedometer2", end: true },
    { label: "Batches", path: "/admin/batches", icon: "bi-collection" },
    { label: "Subjects", path: "/admin/subjects", icon: "bi-journal-bookmark" },
    { label: "Users", path: "/admin/users", icon: "bi-people" },
    { label: "Schedule", path: "/admin/schedule", icon: "bi-calendar-week" },
    { label: "Register Faces", path: "/teacher/enroll", icon: "bi-camera" },
    { label: "Live Attendance", path: "/teacher/attendance", icon: "bi-person-video2" },
    { label: "History", path: "/teacher/history", icon: "bi-clock-history" },
  ],
};

const ROLE_LABEL = {
  student: "Student",
  teacher: "Teacher",
  admin: "Administrator",
};

export default function Sidebar({ role, username, open, onNavigate, onLogout }) {
  const items = NAV_BY_ROLE[role] || [];
  const initial = (username || "?").charAt(0).toUpperCase();

  // Keep the page behind the mobile overlay from scrolling while it's open.
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  // If the viewport grows past the mobile breakpoint while the menu is
  // open (resize or rotation), close it — desktop shows the sidebar
  // permanently anyway, so a stale "open" state has no visual effect but
  // shouldn't linger in state.
  useEffect(() => {
    if (!open) return;
    const handleResize = () => {
      if (window.innerWidth >= 992) onNavigate?.();
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [open, onNavigate]);

  return (
    <>
      {/* Mobile backdrop — tapping outside the sidebar closes it. Part 3
          will drive `open` from the Topbar's hamburger button. */}
      {open && <div className="sidebar-backdrop d-lg-none" onClick={onNavigate} />}

      <aside className={`app-sidebar${open ? " app-sidebar--open" : ""}`}>
        <div className="app-sidebar__profile">
          <div className="app-sidebar__avatar">{initial}</div>
          <div className="app-sidebar__profile-name">{username}</div>
          <div className="app-sidebar__profile-role">{ROLE_LABEL[role] || role}</div>
        </div>

        <nav className="app-sidebar__nav">
          {items.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.end}
              onClick={onNavigate}
              className={({ isActive }) =>
                "app-sidebar__link" + (isActive ? " app-sidebar__link--active" : "")
              }
            >
              <i className={`bi ${item.icon} app-sidebar__icon`} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <button className="app-sidebar__logout" onClick={onLogout}>
          <i className="bi bi-box-arrow-right" />
          <span>Log out</span>
        </button>
      </aside>
    </>
  );
}