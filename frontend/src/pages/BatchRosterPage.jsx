import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getBatchRoster } from "../api";

export default function BatchRosterPage() {
  const { batchId } = useParams();
  const [roster, setRoster] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getBatchRoster(batchId)
      .then(setRoster)
      .catch((err) => setError(err.response?.data?.detail || "Failed to load roster."))
      .finally(() => setLoading(false));
  }, [batchId]);

  if (loading) return <div className="container mt-4">Loading...</div>;

  return (
    <div className="container mt-4">
      <h1>Batch Roster</h1>

      {error && <div className="alert alert-danger">{error}</div>}

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
                No students in this batch yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}