import { useEffect, useState } from "react";
import {
  getUsers,
  createTeacher,
  createStudent,
  updateUser,
  deleteUser,
  getBatches,
} from "../api";
import PageHeader from "../components/PageHeader";

const emptyTeacherForm = { user_name: "", email: "", password: "" };
const emptyStudentForm = {
  user_name: "",
  email: "",
  password: "",
  student_code: "",
  student_name: "",
  batch_id: "",
};

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [batches, setBatches] = useState([]);
  const [roleFilter, setRoleFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [formMode, setFormMode] = useState("student"); // "student" | "teacher"
  const [teacherForm, setTeacherForm] = useState(emptyTeacherForm);
  const [studentForm, setStudentForm] = useState(emptyStudentForm);
  const [creating, setCreating] = useState(false);

  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({});

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [userData, batchData] = await Promise.all([
        getUsers(roleFilter || undefined),
        getBatches(),
      ]);
      setUsers(userData);
      setBatches(batchData);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load users.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roleFilter]);

  const handleCreateTeacher = async (e) => {
    e.preventDefault();
    setCreating(true);
    setError("");
    try {
      await createTeacher(teacherForm);
      setTeacherForm(emptyTeacherForm);
      await fetchAll();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to create teacher.");
    } finally {
      setCreating(false);
    }
  };

  const handleCreateStudent = async (e) => {
    e.preventDefault();
    setCreating(true);
    setError("");
    try {
      await createStudent({
        ...studentForm,
        batch_id: studentForm.batch_id ? Number(studentForm.batch_id) : null,
      });
      setStudentForm(emptyStudentForm);
      await fetchAll();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to create student.");
    } finally {
      setCreating(false);
    }
  };

  const startEdit = (user) => {
    setEditingId(user.id);
    setEditForm({
      is_active: user.is_active,
      role: user.role,
      student_name: user.student_name || "",
      batch_id: user.batch_id || "",
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditForm({});
  };

  const handleUpdate = async (userId) => {
    setError("");
    try {
      const payload = {
        is_active: editForm.is_active,
        role: editForm.role,
      };
      // Only meaningful for users with a student profile — backend ignores
      // these fields for teachers/admins anyway, but skip if untouched.
      if (editForm.student_name) payload.student_name = editForm.student_name;
      if (editForm.batch_id !== "") payload.batch_id = Number(editForm.batch_id);

      await updateUser(userId, payload);
      cancelEdit();
      await fetchAll();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to update user.");
    }
  };

  const handleDelete = async (user) => {
    if (!window.confirm(`Delete user "${user.user_name}"? This is permanent and removes their student profile (and attendance history) if they have one.`)) {
      return;
    }
    setError("");
    try {
      await deleteUser(user.id);
      await fetchAll();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to delete user.");
    }
  };

  return (
    <div className="page">
      <PageHeader title="Manage Users" />

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="panel">
          <ul className="nav nav-tabs mb-3">
            <li className="nav-item">
              <button
                className={`nav-link ${formMode === "student" ? "active" : ""}`}
                onClick={() => setFormMode("student")}
              >
                New Student
              </button>
            </li>
            <li className="nav-item">
              <button
                className={`nav-link ${formMode === "teacher" ? "active" : ""}`}
                onClick={() => setFormMode("teacher")}
              >
                New Teacher
              </button>
            </li>
          </ul>

          {formMode === "teacher" ? (
            <form className="row g-2" onSubmit={handleCreateTeacher}>
              <div className="col-md-4">
                <input
                  className="form-control"
                  placeholder="Username"
                  value={teacherForm.user_name}
                  onChange={(e) => setTeacherForm({ ...teacherForm, user_name: e.target.value })}
                  required
                />
              </div>
              <div className="col-md-4">
                <input
                  className="form-control"
                  type="email"
                  placeholder="Email"
                  value={teacherForm.email}
                  onChange={(e) => setTeacherForm({ ...teacherForm, email: e.target.value })}
                  required
                />
              </div>
              <div className="col-md-3">
                <input
                  className="form-control"
                  type="password"
                  placeholder="Password"
                  value={teacherForm.password}
                  onChange={(e) => setTeacherForm({ ...teacherForm, password: e.target.value })}
                  required
                />
              </div>
              <div className="col-md-1">
                <button className="btn btn-primary w-100" type="submit" disabled={creating}>
                  Add
                </button>
              </div>
            </form>
          ) : (
            <form className="row g-2" onSubmit={handleCreateStudent}>
              <div className="col-md-3">
                <input
                  className="form-control"
                  placeholder="Username"
                  value={studentForm.user_name}
                  onChange={(e) => setStudentForm({ ...studentForm, user_name: e.target.value })}
                  required
                />
              </div>
              <div className="col-md-3">
                <input
                  className="form-control"
                  type="email"
                  placeholder="Email"
                  value={studentForm.email}
                  onChange={(e) => setStudentForm({ ...studentForm, email: e.target.value })}
                  required
                />
              </div>
              <div className="col-md-2">
                <input
                  className="form-control"
                  type="password"
                  placeholder="Password"
                  value={studentForm.password}
                  onChange={(e) => setStudentForm({ ...studentForm, password: e.target.value })}
                  required
                />
              </div>
              <div className="col-md-2">
                <input
                  className="form-control"
                  placeholder="Student code"
                  value={studentForm.student_code}
                  onChange={(e) => setStudentForm({ ...studentForm, student_code: e.target.value })}
                  required
                />
              </div>
              <div className="col-md-2">
                <input
                  className="form-control"
                  placeholder="Full name"
                  value={studentForm.student_name}
                  onChange={(e) => setStudentForm({ ...studentForm, student_name: e.target.value })}
                  required
                />
              </div>
              <div className="col-md-3">
                <select
                  className="form-select"
                  value={studentForm.batch_id}
                  onChange={(e) => setStudentForm({ ...studentForm, batch_id: e.target.value })}
                >
                  <option value="">No batch (assign later)</option>
                  {batches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.batch_name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="col-md-2">
                <button className="btn btn-primary w-100" type="submit" disabled={creating}>
                  {creating ? "Adding..." : "Add"}
                </button>
              </div>
            </form>
          )}
      </div>

      <div className="panel">
        <div className="d-flex align-items-center gap-2 mb-3">
          <label className="mb-0">Filter by role:</label>
          <select
            className="form-select"
            style={{ maxWidth: 200 }}
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
          >
            <option value="">All</option>
            <option value="student">Student</option>
            <option value="teacher">Teacher</option>
            <option value="admin">Admin</option>
          </select>
        </div>

        {loading ? (
          <div className="page-loading">Loading...</div>
        ) : (
        <div className="table-responsive">
          <table className="table">
            <thead>
              <tr>
                <th>Username</th>
                <th>Email</th>
                <th>Role</th>
                <th>Active</th>
                <th>Student Code</th>
                <th>Name</th>
                <th>Batch</th>
                <th style={{ width: 220 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isEditing = editingId === u.id;
                return (
                  <tr key={u.id}>
                    <td>{u.user_name}</td>
                    <td>{u.email}</td>
                    <td>
                      {isEditing ? (
                        <select
                          className="form-select form-select-sm"
                          value={editForm.role}
                          onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                        >
                          <option value="student">student</option>
                          <option value="teacher">teacher</option>
                          <option value="admin">admin</option>
                        </select>
                      ) : (
                        u.role
                      )}
                    </td>
                    <td>
                      {isEditing ? (
                        <input
                          type="checkbox"
                          checked={editForm.is_active}
                          onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                        />
                      ) : u.is_active ? (
                        "Yes"
                      ) : (
                        "No"
                      )}
                    </td>
                    <td>{u.student_code || "—"}</td>
                    <td>
                      {isEditing && u.student_code ? (
                        <input
                          className="form-control form-control-sm"
                          value={editForm.student_name}
                          onChange={(e) => setEditForm({ ...editForm, student_name: e.target.value })}
                        />
                      ) : (
                        u.student_name || "—"
                      )}
                    </td>
                    <td>
                      {isEditing && u.student_code ? (
                        <select
                          className="form-select form-select-sm"
                          value={editForm.batch_id}
                          onChange={(e) => setEditForm({ ...editForm, batch_id: e.target.value })}
                        >
                          <option value="">—</option>
                          {batches.map((b) => (
                            <option key={b.id} value={b.id}>
                              {b.batch_name}
                            </option>
                          ))}
                        </select>
                      ) : (
                        u.batch_name || "—"
                      )}
                    </td>
                    <td>
                      {isEditing ? (
                        <>
                          <button className="btn btn-sm btn-success me-2" onClick={() => handleUpdate(u.id)}>
                            Save
                          </button>
                          <button className="btn btn-sm btn-outline-secondary" onClick={cancelEdit}>
                            Cancel
                          </button>
                        </>
                      ) : (
                        <>
                          <button className="btn btn-sm btn-outline-primary me-2" onClick={() => startEdit(u)}>
                            Edit
                          </button>
                          <button className="btn btn-sm btn-outline-danger" onClick={() => handleDelete(u)}>
                            Delete
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
              {users.length === 0 && (
                <tr>
                  <td colSpan={8} className="empty-state">No users found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        )}
      </div>
    </div>
  );
}