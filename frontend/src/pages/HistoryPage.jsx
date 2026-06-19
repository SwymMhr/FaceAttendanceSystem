import { useEffect, useState } from "react";
import { getAttendanceLogs } from "../api";

export default function HistoryPage() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchLogs = async () => {
    try {
      const res = await getAttendanceLogs();
      setLogs(res.data);
    } catch (err) {
      console.error("Failed to load logs:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  return (
    <div className="page">
      <h1>Attendance History</h1>

      {loading ? (
        <p>Loading...</p>
      ) : logs.length === 0 ? (
        <p>No attendance records found.</p>
      ) : (
        <div className="card">
            <div className="table-responsive">
                <table className="table table-striped table-bordered">

                    <thead>
                        <tr>
                        <th>Name</th>
                        <th>Student ID</th>
                        <th>Date</th>
                        <th>Confidence</th>
                        </tr>
                    </thead>

                    <tbody>
                        {logs.map((r)=>(
                        <tr key={r.id}>
                            <td>{r.name}</td>
                            <td>{r.student_id}</td>
                            <td>{r.timestamp}</td>
                            <td>{r.confidence}</td>
                        </tr>
                        ))}
                    </tbody>

                </table>
            </div>
        </div>
      )}
    </div>
  );
}