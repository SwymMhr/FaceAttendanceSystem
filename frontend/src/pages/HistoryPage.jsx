import { useEffect, useState } from "react";
import { getAttendanceLogs } from "../api";
import PageHeader from "../components/PageHeader";

export default function HistoryPage() {
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchLogs = async () => {
    setError("");
    try {
      const data = await getAttendanceLogs();
      setLogs(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load attendance logs.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  return (
    <div className="page">
      <PageHeader title="Attendance History" />

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="panel">
        {loading ? (
          <div className="page-loading">Loading...</div>
        ) : logs.length === 0 ? (
          <div className="empty-state">No attendance records found.</div>
        ) : (
          <div className="table-responsive">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Student ID</th>
                  <th>Subject</th>
                  <th>Date</th>
                  <th>Status</th>
                  <th>Confidence</th>
                  <th>Recorded At</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((r) => (
                  <tr key={r.id}>
                    <td>{r.name}</td>
                    <td>{r.student_id}</td>
                    <td>{r.subject || "—"}</td>
                    <td>{r.date}</td>
                    <td>
                      <span className={`badge ${r.status === "present" ? "bg-success" : "bg-danger"}`}>
                        {r.status}
                      </span>
                    </td>
                    <td>{r.confidence !== null ? r.confidence : "—"}</td>
                    <td>{new Date(r.timestamp).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
