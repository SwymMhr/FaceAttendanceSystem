import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getUsers, deleteUser } from "../api";
import PageHeader from "../components/PageHeader";

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [roleFilter, setRoleFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const data = await getUsers(roleFilter || undefined);
      setUsers(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load users.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roleFilter]);

  const handleDelete = async (user) => {
    if (!window.confirm(`Delete user "${user.full_name}" (${user.email})? This is permanent and removes their student profile (and attendance history) if they have one.`)) {
      return;
    }
    setError("");
    try {
      await deleteUser(user.id);
      await fetchUsers();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to delete user.");
    }
  };

  return (
    <div className="page">
      <PageHeader
        title="Manage Users"
        actions={
          <>
            <Link to="/admin/users/new-student" className="btn btn-primary">
              Add Student
            </Link>
            <Link to="/admin/users/new-teacher" className="btn btn-primary">
              Add Teacher
            </Link>
          </>
        }
      />

      {error && <div className="alert alert-danger">{error}</div>}

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
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Active</th>
                <th style={{ width: 160 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.full_name}</td>
                  <td>{u.email}</td>
                  <td>{u.role}</td>
                  <td>{u.is_active ? "Yes" : "No"}</td>
                  <td>
                    <Link to={`/admin/users/${u.id}/edit`} className="btn btn-sm btn-outline-primary me-2">
                      Edit
                    </Link>
                    <button className="btn btn-sm btn-outline-danger" onClick={() => handleDelete(u)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr>
                  <td colSpan={5} className="empty-state">No users found.</td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
