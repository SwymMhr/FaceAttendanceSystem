import { Routes, Route, NavLink } from "react-router-dom";
import EnrollPage from "./pages/EnrollPage";
import AttendancePage from "./pages/AttendancePage";
import HistoryPage from "./pages/HistoryPage";

export default function App() {
  return (
    <>
      <nav className="navbar navbar-expand-lg navbar-dark bg-dark">
        <div className="container">
          <div className="navbar-nav ms-auto">
            <NavLink className="nav-link" to="/"> Enroll </NavLink>

            <NavLink className="nav-link" to="/attendance"> Live Attendance </NavLink>

            <NavLink className="nav-link" to="/history" > History </NavLink>
          </div>
        </div>
      </nav>
      <Routes>
        <Route path="/" element={<EnrollPage />} />
        <Route path="/attendance" element={<AttendancePage />} />
        <Route path="/history" element={<HistoryPage />} />
      </Routes>
    </>
  );
}