import { useEffect, useState } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { getPeriodAttendance, setPeriodAttendance, finalizePeriod } from "../api";
import PageHeader from "../components/PageHeader";

const STATUS_BADGE = {
  pending: "bg-info text-dark",
  present: "bg-success",
  absent: "bg-danger",
  none: "bg-secondary",
};

const STATUS_LABEL = {
  pending: "Pending review",
  present: "Present",
  absent: "Absent",
  none: "No record yet",
};

export default function PeriodAttendancePage() {
  const { periodId } = useParams();
  const [searchParams] = useSearchParams();
  // Optional ?date=YYYY-MM-DD — defaults to today (handled server-side).
  const date = searchParams.get("date") || undefined;

  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [rowBusy, setRowBusy] = useState({}); // student_id -> bool
  const [finalizing, setFinalizing] = useState(false);
  const [finalizeMessage, setFinalizeMessage] = useState("");

  const fetchRoster = async () => {
    setError("");
    try {
      const data = await getPeriodAttendance(periodId, date);
      setRows(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load this period's attendance.");
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchRoster().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periodId, date]);

  const handleOverride = async (studentId, status) => {
    setRowBusy((prev) => ({ ...prev, [studentId]: true }));
    setError("");
    try {
      const updated = await setPeriodAttendance(periodId, studentId, status, date);
      setRows((prev) =>
        prev.map((r) => (r.student_id === studentId ? { ...r, status: updated.status, confidence: updated.confidence } : r))
      );
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to update that student's attendance.");
    } finally {
      setRowBusy((prev) => ({ ...prev, [studentId]: false }));
    }
  };

  const handleFinalize = async () => {
    setFinalizing(true);
    setFinalizeMessage("");
    setError("");
    try {
      const result = await finalizePeriod(periodId, date);
      const parts = [];
      if (result.auto_confirmed_present?.length) {
        parts.push(`Auto-confirmed present: ${result.auto_confirmed_present.join(", ")}`);
      }
      if (result.newly_marked_absent?.length) {
        parts.push(`Marked absent: ${result.newly_marked_absent.join(", ")}`);
      }
      setFinalizeMessage(parts.length ? parts.join(" · ") : "Nothing left to finalize — everyone already has a record.");
      await fetchRoster();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to finalize this period.");
    } finally {
      setFinalizing(false);
    }
  };

  const pendingCount = rows.filter((r) => r.status === "pending").length;

  return (
    <div className="page">
      <Link to="/teacher" className="btn btn-sm btn-outline-secondary mb-3">
        &larr; Back to dashboard
      </Link>
      <PageHeader
        title="Period Attendance Review"
        subtitle="Confirm or reject camera detections, or mark any student yourself."
      />

      {error && <div className="alert alert-danger">{error}</div>}
      {finalizeMessage && <div className="alert alert-success">{finalizeMessage}</div>}
      {loading && <div className="page-loading">Loading...</div>}

      {!loading && (
        <div className="panel">
          <div className="d-flex align-items-center gap-3 mb-3">
            <button className="btn btn-primary" onClick={handleFinalize} disabled={finalizing}>
              {finalizing ? "Finalizing..." : "Finalize Attendance"}
            </button>
            {pendingCount > 0 && (
              <span className="text-muted small">{pendingCount} student{pendingCount === 1 ? "" : "s"} awaiting review</span>
            )}
          </div>

          <table className="table align-middle">
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Status</th>
                <th>Confidence</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const busy = !!rowBusy[r.student_id];
                return (
                  <tr key={r.student_id}>
                    <td>{r.student_code}</td>
                    <td>{r.student_name}</td>
                    <td>
                      <span className={`badge ${STATUS_BADGE[r.status] || "bg-secondary"}`}>
                        {STATUS_LABEL[r.status] || r.status}
                      </span>
                    </td>
                    <td>{r.confidence != null ? r.confidence.toFixed(4) : "—"}</td>
                    <td>
                      <div className="d-flex gap-2">
                        <button
                          className="btn btn-sm btn-outline-success"
                          disabled={busy || r.status === "present"}
                          onClick={() => handleOverride(r.student_id, "present")}
                        >
                          {r.status === "pending" ? "Confirm Present" : "Mark Present"}
                        </button>
                        <button
                          className="btn btn-sm btn-outline-danger"
                          disabled={busy || r.status === "absent"}
                          onClick={() => handleOverride(r.student_id, "absent")}
                        >
                          {r.status === "pending" ? "Reject (Absent)" : "Mark Absent"}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={5} className="empty-state">No students in this period's batch.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
