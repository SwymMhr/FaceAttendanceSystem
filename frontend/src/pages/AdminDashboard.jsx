import { useEffect, useState } from "react";
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { getAdminOverview } from "../api";

const STAT_CARD_MIN_WIDTH = 160;

function StatCard({ label, value }) {
  return (
    <div className="card text-center" style={{ minWidth: STAT_CARD_MIN_WIDTH }}>
      <div className="card-body">
        <div style={{ fontSize: "2rem", fontWeight: "bold" }}>{value}</div>
        <small className="text-muted">{label}</small>
      </div>
    </div>
  );
}

const TODAY_COLORS = ["#198754", "#dc3545"]; // present, absent

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

  const todayData = overview
    ? [
        { name: "Present", value: overview.today_present_count },
        { name: "Absent", value: overview.today_absent_count },
      ]
    : [];
  const todayTotal = todayData.reduce((sum, d) => sum + d.value, 0);

  return (
    <div className="container mt-4">
      <h1>Admin Overview</h1>

      {error && <div className="alert alert-danger">{error}</div>}

      {overview && (
        <>
          <div className="d-flex gap-3 flex-wrap mt-4">
            <StatCard label="Students" value={overview.total_students} />
            <StatCard label="Teachers" value={overview.total_teachers} />
            <StatCard label="Batches" value={overview.total_batches} />
            <StatCard label="Present Today" value={overview.today_present_count} />
            <StatCard label="Absent Today" value={overview.today_absent_count} />
            <StatCard label="30-Day Attendance %" value={`${overview.overall_percentage_last_30_days}%`} />
          </div>

          <h5 className="mt-4">Today's Attendance</h5>
          {todayTotal === 0 ? (
            <p className="text-muted">No attendance recorded yet today.</p>
          ) : (
            <div style={{ width: "100%", maxWidth: 360, height: 260 }}>
              <ResponsiveContainer>
                <PieChart>
                  <Pie
                    data={todayData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={90}
                    paddingAngle={2}
                  >
                    {todayData.map((entry, i) => (
                      <Cell key={entry.name} fill={TODAY_COLORS[i]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value, name) => [value, name]} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </div>
  );
}