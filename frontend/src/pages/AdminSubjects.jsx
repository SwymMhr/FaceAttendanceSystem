import { useEffect, useState } from "react";
import { getSubjects, createSubject, updateSubject, deleteSubject } from "../api";
import PageHeader from "../components/PageHeader";

export default function AdminSubjects() {
  const [subjects, setSubjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [newCode, setNewCode] = useState("");
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  const [editingId, setEditingId] = useState(null);
  const [editCode, setEditCode] = useState("");
  const [editName, setEditName] = useState("");

  const fetchSubjects = async () => {
    setLoading(true);
    try {
      const data = await getSubjects();
      setSubjects(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load subjects.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSubjects();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newCode.trim() || !newName.trim()) return;
    setCreating(true);
    setError("");
    try {
      await createSubject(newCode.trim(), newName.trim());
      setNewCode("");
      setNewName("");
      await fetchSubjects();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to create subject.");
    } finally {
      setCreating(false);
    }
  };

  const startEdit = (subject) => {
    setEditingId(subject.id);
    setEditCode(subject.subject_code);
    setEditName(subject.subject_name);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditCode("");
    setEditName("");
  };

  const handleUpdate = async (subjectId) => {
    if (!editCode.trim() || !editName.trim()) return;
    setError("");
    try {
      await updateSubject(subjectId, editCode.trim(), editName.trim());
      cancelEdit();
      await fetchSubjects();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to update subject.");
    }
  };

  const handleDelete = async (subject) => {
    if (!window.confirm(`Delete subject "${subject.subject_name}"? This also removes any timetable periods that use it.`)) {
      return;
    }
    setError("");
    try {
      await deleteSubject(subject.id);
      await fetchSubjects();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to delete subject.");
    }
  };

  return (
    <div className="page">
      <PageHeader title="Manage Subjects" />

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="panel" style={{ maxWidth: 560 }}>
        <h2 className="panel-title">New Subject</h2>
        <form className="d-flex gap-2" onSubmit={handleCreate}>
          <input
            className="form-control"
            style={{ maxWidth: 140 }}
            type="text"
            placeholder="Code (CE101)"
            value={newCode}
            onChange={(e) => setNewCode(e.target.value)}
            required
          />
          <input
            className="form-control"
            type="text"
            placeholder="Subject name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            required
          />
          <button className="btn btn-primary" type="submit" disabled={creating}>
            {creating ? "Adding..." : "Add"}
          </button>
        </form>
      </div>

      <div className="panel">
        {loading ? (
          <div className="page-loading">Loading...</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Subject Name</th>
                <th style={{ width: 220 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {subjects.map((s) => (
                <tr key={s.id}>
                  <td>
                    {editingId === s.id ? (
                      <input
                        className="form-control form-control-sm"
                        value={editCode}
                        onChange={(e) => setEditCode(e.target.value)}
                      />
                    ) : (
                      s.subject_code
                    )}
                  </td>
                  <td>
                    {editingId === s.id ? (
                      <input
                        className="form-control form-control-sm"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                      />
                    ) : (
                      s.subject_name
                    )}
                  </td>
                  <td>
                    {editingId === s.id ? (
                      <>
                        <button className="btn btn-sm btn-success me-2" onClick={() => handleUpdate(s.id)}>
                          Save
                        </button>
                        <button className="btn btn-sm btn-outline-secondary" onClick={cancelEdit}>
                          Cancel
                        </button>
                      </>
                    ) : (
                      <>
                        <button className="btn btn-sm btn-outline-primary me-2" onClick={() => startEdit(s)}>
                          Edit
                        </button>
                        <button className="btn btn-sm btn-outline-danger" onClick={() => handleDelete(s)}>
                          Delete
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
              {subjects.length === 0 && (
                <tr>
                  <td colSpan={3} className="empty-state">No subjects yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
