import { useEffect, useState } from "react";
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { getAdminOverview } from "../api";
import PageHeader from "../components/PageHeader";

function StatCard({ label, value }) {
  return (
    <div className="stat-card">
      <div className="stat-card__value">{value}</div>
      <div className="stat-card__label">{label}</div>
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

  const todayData = overview
    ? [
        { name: "Present", value: overview.today_present_count },
        { name: "Absent", value: overview.today_absent_count },
      ]
    : [];
  const todayTotal = todayData.reduce((sum, d) => sum + d.value, 0);

  return (
    <div className="page">
      <PageHeader title="Admin Overview" />

      {error && <div className="alert alert-danger">{error}</div>}
      {loading && <div className="page-loading">Loading....</div>}

      {overview && (
        <>
          <div className="d-flex gap-3 flex-wrap mb-4">
            <StatCard label="Students" value={overview.total_students} />
            <StatCard label="Teachers" value={overview.total_teachers} />
            <StatCard label="Batches" value={overview.total_batches} />
            <StatCard label="Present Today" value={overview.today_present_count} />
            <StatCard label="Absent Today" value={overview.today_absent_count} />
            <StatCard label="30-Day Attendance %" value={`${overview.overall_percentage_last_30_days}%`} />
          </div>

          <div className="panel">
            <h2 className="panel-title">Today's Attendance</h2>
            {todayTotal === 0 ? (
              <div className="empty-state">No attendance recorded today yet.</div>
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
          </div>
        </>
      )}
    </div>
  );
}
