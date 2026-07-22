import { useEffect, useState } from "react";
import { getStudentSummary, getStudentTrend } from "../api";
import AttendanceTrendChart from "../components/AttendanceTrendChart";
import PageHeader from "../components/PageHeader";

export default function StudentDashboard() {
  const [summary, setSummary] = useState(null);
  const [trend, setTrend] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getStudentSummary(), getStudentTrend(14)])
      .then(([summaryData, trendData]) => {
        setSummary(summaryData);
        setTrend(trendData);
      })
      .catch((err) => setError(err.response?.data?.detail || "Failed to load attendance summary."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page">
      <PageHeader title="My Attendance" />

      {error && <div className="alert alert-danger">{error}</div>}
      {loading && <div className="page-loading">Loading...</div>}

      {summary && (
        <>
          <div className="stat-card mb-4" style={{ maxWidth: 220 }}>
            <div className="stat-card__value">{summary.percentage}%</div>
            <div className="stat-card__label">
              Overall attendance — {summary.total_present} present / {summary.total} total
            </div>
          </div>

          <div className="panel">
            <h2 className="panel-title">By Subject</h2>
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
                    <td colSpan={5} className="empty-state">No attendance records yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="panel">
            <h2 className="panel-title">Last 14 Days</h2>
            <AttendanceTrendChart data={trend} />
          </div>
        </>
      )}
    </div>
  );
}
