import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getBatchRoster, getBatchTrend } from "../api";
import AttendanceTrendChart from "../components/AttendanceTrendChart";
import PageHeader from "../components/PageHeader";

export default function BatchRosterPage() {
  const { batchId } = useParams();
  const [roster, setRoster] = useState([]);
  const [trend, setTrend] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  // Date-range filter for the roster table. Empty strings mean "no bound" —
  // getBatchRoster only appends params that are actually set.
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const fetchRoster = async () => {
    setError("");
    try {
      const params = {};
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;
      const data = await getBatchRoster(batchId, params);
      setRoster(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load roster.");
    }
  };

  const fetchTrend = async () => {
    try {
      const data = await getBatchTrend(batchId, 14);
      setTrend(data);
    } catch (err) {
      // Trend is supplementary — don't block the page on it.
      console.error("Failed to load trend:", err);
    }
  };

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchRoster(), fetchTrend()]).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batchId]);

  const handleApplyFilters = (e) => {
    e.preventDefault();
    fetchRoster();
  };

  const handleClearFilters = () => {
    setStartDate("");
    setEndDate("");
    // Refetch with cleared bounds on next tick, once state updates land.
    setTimeout(fetchRoster, 0);
  };

  return (
    <div className="page">
      <PageHeader
        title="Batch Roster"
        subtitle={
          <>
            Read-only summary. To confirm, reject, or force attendance for a class, open its{" "}
            <Link to="/teacher">Review screen</Link>.
          </>
        }
      />

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="panel">
        <form className="row g-2 align-items-end" onSubmit={handleApplyFilters}>
          <div className="col-auto">
            <label className="form-label mb-0 small text-muted">From</label>
            <input
              type="date"
              className="form-control"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>
          <div className="col-auto">
            <label className="form-label mb-0 small text-muted">To</label>
            <input
              type="date"
              className="form-control"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>
          <div className="col-auto">
            <button className="btn btn-primary" type="submit">Apply</button>
          </div>
          <div className="col-auto">
            <button type="button" className="btn btn-outline-secondary" onClick={handleClearFilters}>
              Clear
            </button>
          </div>
        </form>
      </div>

      <div className="panel">
        {loading ? (
          <div className="page-loading">Loading...</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Present</th>
                <th>Absent</th>
                <th>%</th>
              </tr>
            </thead>
            <tbody>
              {roster.map((s) => (
                <tr key={s.student_id}>
                  <td>{s.student_code}</td>
                  <td>{s.student_name}</td>
                  <td>{s.present_count}</td>
                  <td>{s.absent_count}</td>
                  <td>{s.percentage}%</td>
                </tr>
              ))}
              {roster.length === 0 && (
                <tr>
                  <td colSpan={5} className="empty-state">
                    No students in this batch yet, or none match the selected dates.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h2 className="panel-title">Last 14 Days</h2>
        <AttendanceTrendChart data={trend} />
      </div>
    </div>
  );
}
