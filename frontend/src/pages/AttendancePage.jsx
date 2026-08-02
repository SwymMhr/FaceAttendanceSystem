import { useEffect, useRef, useState } from "react";
import API, { getBatches, getTeacherBatches, getRole } from "../api";
import PageHeader from "../components/PageHeader";

// Maps the backend's attendance_status to a Bootstrap badge color. A
// recognized face lands as "pending" — final confirmation happens on the
// period's Review screen (Teacher Dashboard → Today's Classes → Review).
const STATUS_BADGE = {
  pending: "bg-info text-dark",
  skipped: "bg-warning text-dark",
  error: "bg-danger",
  unrecognized: "bg-secondary",
  rejected: "bg-danger text-white",
};

export default function AttendancePage() {
  const videoRef = useRef(null);

  const [batches, setBatches] = useState([]);
  const [batchId, setBatchId] = useState("");

  const [cameraOn, setCameraOn] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    // Admins can run live attendance for any batch; teachers should only
    // see (and only be able to pick) batches they're actually assigned to
    // teach — /admin/batches is admin-only and would 403 for a teacher.
    const role = getRole();
    const loadBatches = role === "admin" ? getBatches() : getTeacherBatches();

    loadBatches
      .then((data) => {
        // /admin/batches returns {id, batch_name}; /teacher/me/batches
        // returns {batch_id, batch_name} — normalize to one shape.
        const normalized = data.map((b) => ({
          id: b.id ?? b.batch_id,
          batch_name: b.batch_name,
        }));
        setBatches(normalized);
      })
      .catch((err) => setError(err.response?.data?.detail || "Failed to load batches."));
  }, []);

  // Switching batches mid-session means the previous results (and any
  // camera stream) belonged to a different class — clear them so nothing
  // from the old batch lingers on screen or gets attributed to the new one.

   const handleBatchChange = (newBatchId) => {
    setBatchId(newBatchId);
    setResults(null);
    setError("");
    const video = videoRef.current;
    if (video?.srcObject) {
      video.srcObject.getTracks().forEach((track) => track.stop());
      video.srcObject = null;
    }
    setCameraOn(false);
  };

  const startCamera = async () => {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      videoRef.current.srcObject = stream;
      setCameraOn(true);
    } catch (err) {
      setError("Couldn't access the camera. Check browser permissions and try again.");
    }
  };

  const captureFrame = () => {
    if (!batchId) {
      setError("Select a batch before capturing — recognition is scoped to one batch at a time.");
      return;
    }

    const video = videoRef.current;
    if (!video || !video.videoWidth) {
      setError("Camera isn't ready yet — start the camera first.");
      return;
    }

    setError("");
    setCapturing(true);
    setResults(null);

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);

    canvas.toBlob(async (blob) => {
      try {
        const formData = new FormData();
        formData.append("image", blob, "frame.jpg");
        formData.append("batch_id", batchId);

        const res = await API.post("/process_frame", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        setResults(res.data.results);
      } catch (err) {
        setError(err.response?.data?.detail || "Failed to process the frame.");
      } finally {
        setCapturing(false);
      }
    }, "image/jpeg");
  };

  return (
    <div className="page">
      <PageHeader
        title="Live Attendance"
        subtitle="Select the batch currently in front of the camera — recognition only matches students in that batch."
      />

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="panel">
        <div className="mb-3" style={{ maxWidth: 320 }}>
          <label className="form-label">Batch</label>
          <select
            className="form-select"
            value={batchId}
            onChange={(e) => handleBatchChange(e.target.value)}
          >
            <option value="">Select batch...</option>
            {batches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.batch_name}
              </option>
            ))}
          </select>
        </div>

        <div className="d-flex gap-2 mb-3">
          <button
            className="btn btn-primary"
            onClick={startCamera}
            disabled={cameraOn || !batchId}
          >
            {cameraOn ? "Camera On" : "Start Camera"}
          </button>
          <button className="btn btn-success" onClick={captureFrame} disabled={!cameraOn || capturing}>
            {capturing ? "Processing..." : "Capture Frame"}
          </button>
        </div>
        {!batchId && (
          <div className="small text-muted mb-3">
            {batches.length === 0
              ? "You're not assigned to teach any batch yet — check with an admin."
              : "Select a batch above to enable the camera."}
          </div>
        )}

        <div style={{ maxWidth: 480 }}>
          <video ref={videoRef} autoPlay playsInline className="w-100 rounded border" />
        </div>
      </div>

      {results !== null && (
        <div className="panel">
          <h2 className="panel-title">Result</h2>
          {results.length === 0 ? (
            <div className="empty-state">No faces detected in that frame.</div>
          ) : (
            <ul className="list-group" style={{ maxWidth: 560 }}>
              {results.map((r, i) => (
                <li key={i} className="list-group-item">
                  <div className="d-flex justify-content-between align-items-center">
                    <span className="fw-bold">{r.name}</span>
                    <span className={`badge ${STATUS_BADGE[r.attendance_status] || "bg-secondary"}`}>
                      {r.attendance_status}
                    </span>
                  </div>
                  <div className="small text-muted">
                    Confidence: {r.confidence}
                    {r.subject && <> · {r.subject}</>}
                  </div>
                  {r.message && <div className="small mt-1">{r.message}</div>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}