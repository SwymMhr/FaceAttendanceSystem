import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getTeacherToday, getTeacherBatches, finalizePeriod } from "../api";
import PageHeader from "../components/PageHeader";

export default function TeacherDashboard() {
  const [today, setToday] = useState([]);
  const [batches, setBatches] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  // Per-period_id state for the "Finalize Attendance" action, keyed by id:
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
      const parts = [];
      if (result.auto_confirmed_present?.length) {
        parts.push(`Confirmed present: ${result.auto_confirmed_present.join(", ")}`);
      }
      if (result.newly_marked_absent?.length) {
        parts.push(`Marked absent: ${result.newly_marked_absent.join(", ")}`);
      }
      const message = parts.length ? parts.join(" · ") : "Nothing to finalize — everyone already has a record for today.";
      setFinalizeState((prev) => ({ ...prev, [periodId]: { status: "done", message } }));
    } catch (err) {
      const message = err.response?.data?.detail || "Failed to finalize this period.";
      setFinalizeState((prev) => ({ ...prev, [periodId]: { status: "error", message } }));
    }
  };

  return (
    <div className="page">
      <PageHeader title="Teacher Dashboard" />

      {error && <div className="alert alert-danger">{error}</div>}
      {loading && <div className="page-loading">Loading...</div>}

      {!loading && (
        <>
          <div className="panel">
            <h2 className="panel-title">Today's Classes</h2>
            {today.length === 0 ? (
              <div className="empty-state">No classes scheduled today.</div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Subject</th>
                    <th>Batch</th>
                    <th style={{ width: 340 }}>Attendance</th>
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
                          <div className="d-flex gap-2">
                            <Link to={`/teacher/period/${p.period_id}`} className="btn btn-sm btn-outline-primary">
                              Review
                            </Link>
                            <button
                              className="btn btn-sm btn-outline-secondary"
                              onClick={() => handleFinalize(p.period_id)}
                              disabled={state?.status === "pending"}
                            >
                              {state?.status === "pending" ? "Finalizing..." : "Finalize Attendance"}
                            </button>
                          </div>
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
          </div>

          <div className="panel">
            <h2 className="panel-title">My Batches</h2>
            {batches.length === 0 ? (
              <div className="empty-state">No batches assigned yet.</div>
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
        </>
      )}
    </div>
  );
}
