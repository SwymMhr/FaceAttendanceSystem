import { useEffect, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { getBatches, createPeriodSlot } from "../api";
import PageHeader from "../components/PageHeader";

export default function AddPeriodSlotPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const preselectedBatchId = searchParams.get("batch") || "";

  const [batches, setBatches] = useState([]);
  const [form, setForm] = useState({
    batch_id: preselectedBatchId,
    start_time: "",
    end_time: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getBatches()
      .then((data) => {
        setBatches(data);
        // If nothing came in via ?batch=, default to the first batch once loaded.
        setForm((f) => (f.batch_id ? f : { ...f, batch_id: data[0] ? String(data[0].id) : "" }));
      })
      .catch((err) => setError(err.response?.data?.detail || "Failed to load batches."));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.batch_id || !form.start_time || !form.end_time) return;

    if (form.end_time <= form.start_time) {
      setError("End time must be after start time.");
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      await createPeriodSlot(Number(form.batch_id), {
        start_time: form.start_time,
        end_time: form.end_time,
      });
      navigate(`/admin/schedule?batch=${form.batch_id}`);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to add period slot.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page">
      <Link to="/admin/schedule" className="btn btn-sm btn-outline-secondary mb-3">
        &larr; Back to Schedule
      </Link>
      <PageHeader
        title="Add Period"
        subtitle="Add a new time slot to a batch's timetable. The period number is assigned automatically — this just becomes the next period for that batch."
      />

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="panel">
        <form onSubmit={handleSubmit} style={{ maxWidth: 480 }}>
          <div className="mb-3">
            <label className="form-label">Batch</label>
            <select
              className="form-select"
              value={form.batch_id}
              onChange={(e) => setForm({ ...form, batch_id: e.target.value })}
              required
            >
              <option value="">Select batch...</option>
              {batches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.batch_name}
                </option>
              ))}
            </select>
          </div>

          <div className="row g-2">
            <div className="col-6 mb-3">
              <label className="form-label">Start Time</label>
              <input
                type="time"
                className="form-control"
                value={form.start_time}
                onChange={(e) => setForm({ ...form, start_time: e.target.value })}
                required
              />
            </div>
            <div className="col-6 mb-3">
              <label className="form-label">End Time</label>
              <input
                type="time"
                className="form-control"
                value={form.end_time}
                onChange={(e) => setForm({ ...form, end_time: e.target.value })}
                required
              />
            </div>
          </div>

          <button className="btn btn-primary" type="submit" disabled={submitting}>
            {submitting ? "Adding..." : "Add Period"}
          </button>
        </form>
      </div>
    </div>
  );
}