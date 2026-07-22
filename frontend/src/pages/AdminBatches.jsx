import { useEffect, useState } from "react";
import { getBatches, createBatch, updateBatch, deleteBatch } from "../api";
import PageHeader from "../components/PageHeader";

export default function AdminBatches() {
  const [batches, setBatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState("");

  const fetchBatches = async () => {
    setLoading(true);
    try {
      const data = await getBatches();
      setBatches(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load batches.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBatches();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    setError("");
    try {
      await createBatch(newName.trim());
      setNewName("");
      await fetchBatches();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to create batch.");
    } finally {
      setCreating(false);
    }
  };

  const startEdit = (batch) => {
    setEditingId(batch.id);
    setEditName(batch.batch_name);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditName("");
  };

  const handleUpdate = async (batchId) => {
    if (!editName.trim()) return;
    setError("");
    try {
      await updateBatch(batchId, editName.trim());
      cancelEdit();
      await fetchBatches();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to update batch.");
    }
  };

  const handleDelete = async (batch) => {
    if (!window.confirm(`Delete batch "${batch.batch_name}"? Students keep their record but lose this batch, and any timetable periods for it are removed.`)) {
      return;
    }
    setError("");
    try {
      await deleteBatch(batch.id);
      await fetchBatches();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to delete batch.");
    }
  };

  return (
    <div className="page">
      <PageHeader title="Manage Batches" />

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="panel" style={{ maxWidth: 480 }}>
        <h2 className="panel-title">New Batch</h2>
        <form className="d-flex gap-2" onSubmit={handleCreate}>
          <input
            className="form-control"
            type="text"
            placeholder="e.g. 2024 Software"
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
                <th>ID</th>
                <th>Batch Name</th>
                <th style={{ width: 220 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {batches.map((b) => (
                <tr key={b.id}>
                  <td>{b.id}</td>
                  <td>
                    {editingId === b.id ? (
                      <input
                        className="form-control form-control-sm"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                      />
                    ) : (
                      b.batch_name
                    )}
                  </td>
                  <td>
                    {editingId === b.id ? (
                      <>
                        <button className="btn btn-sm btn-success me-2" onClick={() => handleUpdate(b.id)}>
                          Save
                        </button>
                        <button className="btn btn-sm btn-outline-secondary" onClick={cancelEdit}>
                          Cancel
                        </button>
                      </>
                    ) : (
                      <>
                        <button className="btn btn-sm btn-outline-primary me-2" onClick={() => startEdit(b)}>
                          Rename
                        </button>
                        <button className="btn btn-sm btn-outline-danger" onClick={() => handleDelete(b)}>
                          Delete
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
              {batches.length === 0 && (
                <tr>
                  <td colSpan={3} className="empty-state">No batches yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
