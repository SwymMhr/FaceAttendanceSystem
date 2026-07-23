import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { createStudent, getBatches } from "../api";
import PageHeader from "../components/PageHeader";
import PasswordInput from "../components/PasswordInput";

export default function AddStudentPage() {
  const navigate = useNavigate();
  const [batches, setBatches] = useState([]);
  const [form, setForm] = useState({
    email: "",
    password: "",
    student_code: "",
    student_name: "",
    batch_id: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getBatches()
      .then(setBatches)
      .catch((err) => setError(err.response?.data?.detail || "Failed to load batches."));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await createStudent({
        ...form,
        batch_id: form.batch_id ? Number(form.batch_id) : null,
      });
      navigate("/admin/users");
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to create student.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page">
      <Link to="/admin/users" className="btn btn-sm btn-outline-secondary mb-3">
        &larr; Back to Users
      </Link>
      <PageHeader title="Add Student" />

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="panel">
        <form onSubmit={handleSubmit} style={{ maxWidth: 480 }} autoComplete="off">
          <div className="mb-3">
            <label className="form-label">Email</label>
            <input
              className="form-control"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              autoComplete="off"
              data-lpignore="true"
              data-1p-ignore
              required
            />
          </div>

          <div className="mb-3">
            <label className="form-label">Password</label>
            <PasswordInput
              className="form-control"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required
            />
          </div>

          <div className="mb-3">
            <label className="form-label">Student Code</label>
            <input
              className="form-control"
              value={form.student_code}
              onChange={(e) => setForm({ ...form, student_code: e.target.value })}
              required
            />
          </div>

          <div className="mb-3">
            <label className="form-label">Full Name</label>
            <input
              className="form-control"
              value={form.student_name}
              onChange={(e) => setForm({ ...form, student_name: e.target.value })}
              required
            />
          </div>

          <div className="mb-3">
            <label className="form-label">Batch</label>
            <select
              className="form-select"
              value={form.batch_id}
              onChange={(e) => setForm({ ...form, batch_id: e.target.value })}
            >
              <option value="">No batch (assign later)</option>
              {batches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.batch_name}
                </option>
              ))}
            </select>
          </div>

          <button className="btn btn-primary" type="submit" disabled={submitting}>
            {submitting ? "Adding..." : "Add Student"}
          </button>
        </form>
      </div>
    </div>
  );
}
