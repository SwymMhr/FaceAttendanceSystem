import { useEffect, useState } from "react";
import { getStudentHistory } from "../api";

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
    <div className="container mt-4">
      <h1>My Attendance History</h1>

      {error && <div className="alert alert-danger">{error}</div>}

      {loading ? (
        <p>Loading...</p>
      ) : logs.length === 0 ? (
        <p className="text-muted">No attendance records found.</p>
      ) : (
        <div className="card">
          <div className="table-responsive">
            <table className="table table-striped table-bordered mb-0">
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
          </div>
        </div>
      )}
    </div>
  );
}