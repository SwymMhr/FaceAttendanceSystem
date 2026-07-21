import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getTeacherToday, getTeacherBatches } from "../api";

export default function TeacherDashboard() {
  const [today, setToday] = useState([]);
  const [batches, setBatches] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getTeacherToday(), getTeacherBatches()])
      .then(([todayData, batchesData]) => {
        setToday(todayData);
        setBatches(batchesData);
      })
      .catch((err) => setError(err.response?.data?.detail || "Failed to load dashboard."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="container mt-4">Loading...</div>;

  return (
    <div className="container mt-4">
      <h1>Teacher Dashboard</h1>

      {error && <div className="alert alert-danger">{error}</div>}

      <h5 className="mt-4">Today's Classes</h5>
      {today.length === 0 ? (
        <p className="text-muted">No classes scheduled today.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Subject</th>
              <th>Batch</th>
            </tr>
          </thead>
          <tbody>
            {today.map((p) => (
              <tr key={p.period_id}>
                <td>{p.start_time} - {p.end_time}</td>
                <td>{p.subject_code} — {p.subject_name}</td>
                <td>{p.batch_name}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h5 className="mt-4">My Batches</h5>
      {batches.length === 0 ? (
        <p className="text-muted">No batches assigned yet.</p>
      ) : (
        <ul className="list-group" style={{ maxWidth: 400 }}>
          {batches.map((b) => (
            <li key={b.batch_id} className="list-group-item d-flex justify-content-between align-items-center">
              {b.batch_name}
              <Link to={`/teacher/batch/${b.batch_id}`} className="btn btn-sm btn-outline-primary">
                View roster
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}