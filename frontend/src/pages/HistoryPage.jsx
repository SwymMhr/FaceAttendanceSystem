import { useEffect, useMemo, useState } from "react";
import { getAttendanceLogs, getAttendanceFilterOptions } from "../api";
import PageHeader from "../components/PageHeader";

const EMPTY_FILTERS = {
  startDate: "",
  endDate: "",
  studentName: "",
  batchId: "",
  teacherId: "",
};

export default function HistoryPage() {
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const [batches, setBatches] = useState([]);
  const [teachers, setTeachers] = useState([]);

  // Draft = what's currently typed/selected in the form.
  // Applied = the filters actually sent to the last fetch — kept separate
  // so typing a name doesn't refetch on every keystroke.
  const [draft, setDraft] = useState(EMPTY_FILTERS);
  const [applied, setApplied] = useState(EMPTY_FILTERS);

  const activeFilterCount = useMemo(
    () => Object.values(applied).filter(Boolean).length,
    [applied]
  );

  // Reference data for the Batch / Teacher dropdowns — loaded once.
  useEffect(() => {
    getAttendanceFilterOptions()
      .then((data) => {
        setBatches(data.batches || []);
        setTeachers(data.teachers || []);
      })
      .catch(() => {
        // Non-fatal — filters just fall back to text/date-only if this fails.
      });
  }, []);

  const fetchLogs = async (filters) => {
    setLoading(true);
    setError("");
    try {
      const data = await getAttendanceLogs(filters);
      setLogs(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load attendance logs.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs(applied);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applied]);

  const handleApply = (e) => {
    e.preventDefault();
    setApplied(draft);
  };

  const handleReset = () => {
    setDraft(EMPTY_FILTERS);
    setApplied(EMPTY_FILTERS);
  };

  return (
    <div className="page">
      <PageHeader
        title="Attendance History"
      />

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="panel">
        <form className="row g-3 align-items-end" onSubmit={handleApply}>
          <div className="col-6 col-md-3 col-lg-2">
            <label className="form-label">Start Date</label>
            <input
              type="date"
              className="form-control"
              value={draft.startDate}
              max={draft.endDate || undefined}
              onChange={(e) => setDraft({ ...draft, startDate: e.target.value })}
            />
          </div>
          <div className="col-6 col-md-3 col-lg-2">
            <label className="form-label">End Date</label>
            <input
              type="date"
              className="form-control"
              value={draft.endDate}
              min={draft.startDate || undefined}
              onChange={(e) => setDraft({ ...draft, endDate: e.target.value })}
            />
          </div>
          <div className="col-12 col-md-3 col-lg-3">
            <label className="form-label">Student Name</label>
            <input
              type="text"
              className="form-control"
              placeholder="Search by name..."
              value={draft.studentName}
              onChange={(e) => setDraft({ ...draft, studentName: e.target.value })}
            />
          </div>
          <div className="col-6 col-md-3 col-lg-2">
            <label className="form-label">Batch</label>
            <select
              className="form-select"
              value={draft.batchId}
              onChange={(e) => setDraft({ ...draft, batchId: e.target.value })}
            >
              <option value="">All batches</option>
              {batches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.batch_name}
                </option>
              ))}
            </select>
          </div>
          <div className="col-6 col-md-3 col-lg-2">
            <label className="form-label">Teacher</label>
            <select
              className="form-select"
              value={draft.teacherId}
              onChange={(e) => setDraft({ ...draft, teacherId: e.target.value })}
            >
              <option value="">All teachers</option>
              {teachers.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
          <div className="col-12 col-lg-1 d-flex gap-2">
            <button type="submit" className="btn btn-primary flex-fill">
              Apply
            </button>
          </div>
          {activeFilterCount > 0 && (
            <div className="col-12">
              <button
                type="button"
                className="btn btn-sm btn-outline-secondary"
                onClick={handleReset}
              >
                Clear filters ({activeFilterCount})
              </button>
            </div>
          )}
        </form>
      </div>

      <div className="panel">
        {loading ? (
          <div className="page-loading">Loading...</div>
        ) : logs.length === 0 ? (
          <div className="empty-state">
            No attendance records found{activeFilterCount > 0 ? " for these filters." : "."}
          </div>
        ) : (
          <div className="table-responsive">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Student ID</th>
                  <th>Batch</th>
                  <th>Subject</th>
                  <th>Teacher</th>
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
                    <td>{r.batch_name || "—"}</td>
                    <td>{r.subject || "—"}</td>
                    <td>{r.teacher_name || "—"}</td>
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