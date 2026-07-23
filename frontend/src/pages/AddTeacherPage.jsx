import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { createTeacher } from "../api";
import PageHeader from "../components/PageHeader";
import PasswordInput from "../components/PasswordInput";

export default function AddTeacherPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await createTeacher(form);
      navigate("/admin/users");
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to create teacher.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page">
      <Link to="/admin/users" className="btn btn-sm btn-outline-secondary mb-3">
        &larr; Back to Users
      </Link>
      <PageHeader title="Add Teacher" />

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="panel">
        <form onSubmit={handleSubmit} style={{ maxWidth: 480 }} autoComplete="off">
          <div className="mb-3">
            <label className="form-label">Full Name</label>
            <input
              className="form-control"
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              required
            />
          </div>

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

          <button className="btn btn-primary" type="submit" disabled={submitting}>
            {submitting ? "Adding..." : "Add Teacher"}
          </button>
        </form>
      </div>
    </div>
  );
}
