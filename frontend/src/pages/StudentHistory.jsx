import { useEffect, useState } from "react";
import { getStudentHistory } from "../api";
import PageHeader from "../components/PageHeader";

export default function StudentHistory() {
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStudentHistory(100)
      .then(setLogs)
      .catch((err) => setError(err.response?.data?.detail || "Failed to load attendance history."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page">
      <PageHeader title="My Attendance History" />

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="panel">
        {loading ? (
          <div className="page-loading">Loading...</div>
        ) : logs.length === 0 ? (
          <div className="empty-state">No attendance records found.</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Subject</th>
                <th>Status</th>
                <th>Recorded At</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((r, i) => (
                <tr key={i}>
                  <td>{r.date}</td>
                  <td>{r.subject_code} — {r.subject_name}</td>
                  <td>
                    <span className={`badge ${r.status === "present" ? "bg-success" : "bg-danger"}`}>
                      {r.status}
                    </span>
                  </td>
                  <td>{new Date(r.timestamp).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
