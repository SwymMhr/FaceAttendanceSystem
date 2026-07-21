import { useEffect, useState } from "react";
import { getAdminOverview } from "../api";

export default function AdminDashboard() {
  const [overview, setOverview] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAdminOverview()
      .then(setOverview)
      .catch((err) => setError(err.response?.data?.detail || "Failed to load overview."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="container mt-4">Loading...</div>;

  const StatCard = ({ label, value }) => (
    <div className="card text-center" style={{ minWidth: 160 }}>
      <div className="card-body">
        <div style={{ fontSize: "2rem", fontWeight: "bold" }}>{value}</div>
        <small className="text-muted">{label}</small>
      </div>
    </div>
  );

  return (
    <div className="container mt-4">
      <h1>Admin Overview</h1>

      {error && <div className="alert alert-danger">{error}</div>}

      {overview && (
        <div className="d-flex gap-3 flex-wrap mt-4">
          <StatCard label="Students" value={overview.total_students} />
          <StatCard label="Teachers" value={overview.total_teachers} />
          <StatCard label="Batches" value={overview.total_batches} />
          <StatCard label="Present Today" value={overview.today_present_count} />
          <StatCard label="Absent Today" value={overview.today_absent_count} />
          <StatCard label="30-Day Attendance %" value={`${overview.overall_percentage_last_30_days}%`} />
        </div>
      )}
    </div>
  );
}