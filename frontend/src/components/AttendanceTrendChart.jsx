import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

/**
 * Renders daily present/absent counts as stacked bars, with the
 * attendance percentage overlaid as a line on a secondary axis.
 *
 * data: array of { date, present_count, absent_count, percentage }
 * — exactly what /student/me/trend, /teacher/batch/:id/trend return.
 */
export default function AttendanceTrendChart({ data }) {
  if (!data || data.length === 0) {
    return <p className="text-muted">No attendance data yet.</p>;
  }

  // Trim to "Jul 21" style labels so the x-axis doesn't get crowded on
  // longer ranges.
  const chartData = data.map((d) => ({
    ...d,
    label: new Date(d.date).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
  }));

  return (
    <div style={{ width: "100%", height: 300 }}>
      <ResponsiveContainer>
        <ComposedChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="label" fontSize={12} />
          <YAxis
            yAxisId="count"
            allowDecimals={false}
            fontSize={12}
            label={{ value: "Students", angle: -90, position: "insideLeft", fontSize: 12 }}
          />
          <YAxis
            yAxisId="percentage"
            orientation="right"
            domain={[0, 100]}
            fontSize={12}
            label={{ value: "%", angle: 90, position: "insideRight", fontSize: 12 }}
          />
          <Tooltip
            formatter={(value, name) => {
              if (name === "percentage") return [`${value}%`, "Attendance %"];
              if (name === "present_count") return [value, "Present"];
              if (name === "absent_count") return [value, "Absent"];
              return [value, name];
            }}
            labelFormatter={(label) => label}
          />
          <Legend
            formatter={(value) => {
              if (value === "present_count") return "Present";
              if (value === "absent_count") return "Absent";
              if (value === "percentage") return "Attendance %";
              return value;
            }}
          />
          <Bar yAxisId="count" dataKey="present_count" stackId="a" fill="#198754" radius={[0, 0, 0, 0]} />
          <Bar yAxisId="count" dataKey="absent_count" stackId="a" fill="#dc3545" radius={[4, 4, 0, 0]} />
          <Line
            yAxisId="percentage"
            type="monotone"
            dataKey="percentage"
            stroke="#0d6efd"
            strokeWidth={2}
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}