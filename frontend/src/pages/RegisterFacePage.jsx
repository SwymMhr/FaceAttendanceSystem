import { useEffect, useState } from "react";
import { getBatches, getBatchStudents, getEmbeddingCount, registerFace } from "../api";

export default function RegisterFacePage() {
  const [batches, setBatches] = useState([]);
  const [students, setStudents] = useState([]);

  const [selectedBatchId, setSelectedBatchId] = useState("");
  // This holds a Student.id (tbl_students.id) — NOT the login account id.
  // register_face / get_embedding_count both look students up by that id.
  const [selectedStudentId, setSelectedStudentId] = useState("");
  const [embeddingCount, setEmbeddingCount] = useState(null);

  const [images, setImages] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const [loadingBatches, setLoadingBatches] = useState(true);
  const [loadingStudents, setLoadingStudents] = useState(false);

  // Load batches once.
  useEffect(() => {
    getBatches()
      .then(setBatches)
      .catch((err) => setError(err.response?.data?.detail || "Failed to load batches."))
      .finally(() => setLoadingBatches(false));
  }, []);

  // Reload the student dropdown whenever the batch changes.
  useEffect(() => {
    setSelectedStudentId("");
    setEmbeddingCount(null);
    setStudents([]);
    if (!selectedBatchId) return;

    setLoadingStudents(true);
    getBatchStudents(selectedBatchId)
      .then(setStudents)
      .catch((err) => setError(err.response?.data?.detail || "Failed to load students."))
      .finally(() => setLoadingStudents(false));
  }, [selectedBatchId]);

  // Show how many photos are already registered once a student is picked.
  useEffect(() => {
    setEmbeddingCount(null);
    setResult(null);
    if (!selectedStudentId) return;

    getEmbeddingCount(selectedStudentId)
      .then((data) => setEmbeddingCount(data.embeddings_count))
      .catch(() => setEmbeddingCount(null));
  }, [selectedStudentId]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedStudentId || images.length === 0) return;

    setSubmitting(true);
    setError("");
    setResult(null);
    try {
      const data = await registerFace(selectedStudentId, images);
      setResult(data);
      setEmbeddingCount(data.total_embeddings);
      setImages([]);
      // Reset the file input visually too.
      document.getElementById("register-face-file-input").value = "";
    } catch (err) {
      setError(err.response?.data?.detail || "Face registration failed.");
    } finally {
      setSubmitting(false);
    }
  };

  const selectedStudent = students.find(
    (s) => String(s.student_db_id) === String(selectedStudentId)
  );

  return (
    <div className="container mt-4">
      <h1>Register Student Faces</h1>
      <p className="text-muted">
        Add face photos for a student who's already been created in Users.
        Pick their batch, then their name, then upload one or more clear
        photos of their face.
      </p>

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="card" style={{ maxWidth: 560 }}>
        <div className="card-body">
          <div className="mb-3">
            <label className="form-label">Batch</label>
            <select
              className="form-select"
              value={selectedBatchId}
              onChange={(e) => setSelectedBatchId(e.target.value)}
              disabled={loadingBatches}
            >
              <option value="">
                {loadingBatches ? "Loading batches..." : "Select a batch..."}
              </option>
              {batches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.batch_name}
                </option>
              ))}
            </select>
          </div>

          <div className="mb-3">
            <label className="form-label">Student</label>
            <select
              className="form-select"
              value={selectedStudentId}
              onChange={(e) => setSelectedStudentId(e.target.value)}
              disabled={!selectedBatchId || loadingStudents}
            >
              <option value="">
                {!selectedBatchId
                  ? "Select a batch first..."
                  : loadingStudents
                  ? "Loading students..."
                  : students.length === 0
                  ? "No students in this batch"
                  : "Select a student..."}
              </option>
              {students.map((s) => (
                // value is Student.id (student_db_id), not the login-account id —
                // that's what the face-registration endpoints actually key off.
                <option key={s.id} value={s.student_db_id}>
                  {s.student_code} — {s.student_name}
                </option>
              ))}
            </select>
            {selectedStudent && embeddingCount !== null && (
              <div className="form-text">
                {embeddingCount === 0
                  ? "No photos registered yet."
                  : `${embeddingCount} photo${embeddingCount === 1 ? "" : "s"} currently registered.`}
              </div>
            )}
          </div>

          <form onSubmit={handleSubmit}>
            <div className="mb-3">
              <label className="form-label">Photos</label>
              <input
                id="register-face-file-input"
                className="form-control"
                type="file"
                accept="image/*"
                multiple
                disabled={!selectedStudentId}
                onChange={(e) => setImages(Array.from(e.target.files))}
              />
            </div>

            {images.length > 0 && (
              <ul className="list-group mb-3">
                {images.map((img, i) => (
                  <li key={i} className="list-group-item py-1">
                    {img.name}
                  </li>
                ))}
              </ul>
            )}

            <button
              className="btn btn-primary"
              type="submit"
              disabled={!selectedStudentId || images.length === 0 || submitting}
            >
              {submitting ? "Registering..." : "Register Photos"}
            </button>
          </form>

          {result && (
            <div className="alert alert-success mt-3 mb-0">
              Registered {result.images_registered} photo
              {result.images_registered === 1 ? "" : "s"} for {result.student_name}.
              {result.images_skipped_no_face > 0 && (
                <> {result.images_skipped_no_face} photo
                  {result.images_skipped_no_face === 1 ? "" : "s"} skipped — no face detected.</>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}