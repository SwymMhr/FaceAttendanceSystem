import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { getUser, updateUser, getBatches } from "../api";
import PageHeader from "../components/PageHeader";
import PasswordInput from "../components/PasswordInput";

export default function EditUserPage() {
  const { userId } = useParams();
  const navigate = useNavigate();

  const [batches, setBatches] = useState([]);
  const [form, setForm] = useState(null); // null until the user loads
  const [isStudent, setIsStudent] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    Promise.all([getUser(userId), getBatches()])
      .then(([user, batchData]) => {
        setBatches(batchData);
        setIsStudent(!!user.student_code);
        setForm({
          email: user.email,
          password: "",
          role: user.role,
          is_active: user.is_active,
          full_name: user.full_name || "",
          student_code: user.student_code || "",
          student_name: user.student_name || "",
          batch_id: user.batch_id || "",
        });
      })
      .catch((err) => setError(err.response?.data?.detail || "Failed to load user."))
      .finally(() => setLoading(false));
  }, [userId]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const payload = {
        email: form.email,
        is_active: form.is_active,
        role: form.role,
        batch_id: form.batch_id ? Number(form.batch_id) : null,
      };
      if (form.password) payload.password = form.password;
      if (isStudent) {
        payload.student_code = form.student_code;
        payload.student_name = form.student_name;
      } else {
        payload.full_name = form.full_name;
      }

      await updateUser(userId, payload);
      navigate("/admin/users");
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to update user.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page">
      <Link to="/admin/users" className="btn btn-sm btn-outline-secondary mb-3">
        &larr; Back to Users
      </Link>
      <PageHeader title="Edit User" />

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="panel">
        {loading ? (
          <div className="page-loading">Loading...</div>
        ) : (
          <form onSubmit={handleSubmit} style={{ maxWidth: 480 }} autoComplete="off">
            {isStudent ? (
              <div className="mb-3">
                <label className="form-label">Full Name</label>
                <input
                  className="form-control"
                  value={form.student_name}
                  onChange={(e) => setForm({ ...form, student_name: e.target.value })}
                  required
                />
              </div>
            ) : (
              <div className="mb-3">
                <label className="form-label">Full Name</label>
                <input
                  className="form-control"
                  value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                  required
                />
              </div>
            )}

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
              <label className="form-label">New Password</label>
              <PasswordInput
                className="form-control"
                placeholder="New Password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            </div>

            <div className="mb-3">
              <label className="form-label">Role</label>
              <select
                className="form-select"
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
              >
                <option value="student">student</option>
                <option value="teacher">teacher</option>
                <option value="admin">admin</option>
              </select>
            </div>

            <div className="mb-3 form-check">
              <input
                className="form-check-input"
                type="checkbox"
                id="edit-user-active"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              />
              <label className="form-check-label" htmlFor="edit-user-active">
                Active
              </label>
            </div>

            {isStudent && (
              <>
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
                  <label className="form-label">Batch</label>
                  <select
                    className="form-select"
                    value={form.batch_id}
                    onChange={(e) => setForm({ ...form, batch_id: e.target.value })}
                  >
                    <option value="">No batch</option>
                    {batches.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.batch_name}
                      </option>
                    ))}
                  </select>
                </div>
              </>
            )}

            <button className="btn btn-primary" type="submit" disabled={submitting}>
              {submitting ? "Saving..." : "Save Changes"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
