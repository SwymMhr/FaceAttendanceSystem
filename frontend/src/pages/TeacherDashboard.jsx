import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getTeacherToday, getTeacherBatches, finalizePeriod } from "../api";

export default function TeacherDashboard() {
  const [today, setToday] = useState([]);
  const [batches, setBatches] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  // Per-period_id state for the "Finalize Absences" action, keyed by id:
  // { status: "pending" | "done" | "error", message: string }
  const [finalizeState, setFinalizeState] = useState({});

  useEffect(() => {
    Promise.all([getTeacherToday(), getTeacherBatches()])
      .then(([todayData, batchesData]) => {
        setToday(todayData);
        setBatches(batchesData);
      })
      .catch((err) => setError(err.response?.data?.detail || "Failed to load dashboard."))
      .finally(() => setLoading(false));
  }, []);

  const handleFinalize = async (periodId) => {
    setFinalizeState((prev) => ({ ...prev, [periodId]: { status: "pending" } }));
    try {
      const result = await finalizePeriod(periodId);
      const names = result.newly_marked_absent;
      const message =
        names.length === 0
          ? "No new absences — everyone already has a record for today."
          : `Marked absent: ${names.join(", ")}`;
      setFinalizeState((prev) => ({ ...prev, [periodId]: { status: "done", message } }));
    } catch (err) {
      const message = err.response?.data?.detail || "Failed to finalize this period.";
      setFinalizeState((prev) => ({ ...prev, [periodId]: { status: "error", message } }));
    }
  };

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
              <th style={{ width: 280 }}>Attendance</th>
            </tr>
          </thead>
          <tbody>
            {today.map((p) => {
              const state = finalizeState[p.period_id];
              return (
                <tr key={p.period_id}>
                  <td>{p.start_time} - {p.end_time}</td>
                  <td>{p.subject_code} — {p.subject_name}</td>
                  <td>{p.batch_name}</td>
                  <td>
                    <button
                      className="btn btn-sm btn-outline-secondary"
                      onClick={() => handleFinalize(p.period_id)}
                      disabled={state?.status === "pending"}
                    >
                      {state?.status === "pending" ? "Finalizing..." : "Finalize Absences"}
                    </button>
                    {state?.status === "done" && (
                      <div className="small text-muted mt-1">{state.message}</div>
                    )}
                    {state?.status === "error" && (
                      <div className="small text-danger mt-1">{state.message}</div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {today.length > 0 && (
        <p className="text-muted small">
          The system finalizes absences automatically a few minutes after each
          period ends — "Finalize Absences" just runs that same check right
          now instead of waiting, e.g. right after class. It's safe to click
          more than once.
        </p>
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