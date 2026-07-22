import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getBatchRoster, getBatchTrend } from "../api";
import AttendanceTrendChart from "../components/AttendanceTrendChart";

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

  if (loading) return <div className="container mt-4">Loading...</div>;

  return (
    <div className="container mt-4">
      <h1>Batch Roster</h1>

      {error && <div className="alert alert-danger">{error}</div>}

      <form className="row g-2 align-items-end mb-4" onSubmit={handleApplyFilters}>
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
              <td colSpan={5} className="text-center text-muted">
                No students in this batch yet, or none match the selected dates.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      <h5 className="mt-4">Last 14 Days</h5>
      <AttendanceTrendChart data={trend} />
    </div>
  );
}