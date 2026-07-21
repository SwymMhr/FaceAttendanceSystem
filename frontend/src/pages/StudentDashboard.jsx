import { useEffect, useState } from "react";
import { getStudentSummary } from "../api";

export default function StudentDashboard() {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStudentSummary()
      .then(setSummary)
      .catch((err) => setError(err.response?.data?.detail || "Failed to load attendance summary."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="container mt-4">Loading...</div>;

  return (
    <div className="container mt-4">
      <h1>My Attendance</h1>

      {error && <div className="alert alert-danger">{error}</div>}

      {summary && (
        <>
          <div className="card mb-4" style={{ maxWidth: 320 }}>
            <div className="card-body text-center">
              <h6 className="text-muted mb-1">Overall Attendance</h6>
              <div style={{ fontSize: "2.5rem", fontWeight: "bold" }}>
                {summary.percentage}%
              </div>
              <small className="text-muted">
                {summary.total_present} present / {summary.total} total
              </small>
            </div>
          </div>

          <h5>By Subject</h5>
          <table className="table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Subject</th>
                <th>Present</th>
                <th>Absent</th>
                <th>%</th>
              </tr>
            </thead>
            <tbody>
              {summary.by_subject.map((s) => (
                <tr key={s.subject_id}>
                  <td>{s.subject_code}</td>
                  <td>{s.subject_name}</td>
                  <td>{s.present_count}</td>
                  <td>{s.absent_count}</td>
                  <td>{s.percentage}%</td>
                </tr>
              ))}
              {summary.by_subject.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-center text-muted">
                    No attendance records yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}