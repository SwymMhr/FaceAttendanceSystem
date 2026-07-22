import { useRef, useState } from "react";
import API from "../api";

// Maps the backend's attendance_status to a Bootstrap badge color, so it's
// obvious at a glance whether a face actually got marked present or not.
const STATUS_BADGE = {
  marked: "bg-success",
  skipped: "bg-warning text-dark",
  error: "bg-danger",
  unrecognized: "bg-secondary",
};

export default function AttendancePage() {
  const videoRef = useRef(null);
  const [cameraOn, setCameraOn] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState("");

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
    <div className="container mt-4">
      <h1>Live Attendance</h1>

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="d-flex gap-2 mb-3">
        <button className="btn btn-primary" onClick={startCamera} disabled={cameraOn}>
          {cameraOn ? "Camera On" : "Start Camera"}
        </button>
        <button className="btn btn-success" onClick={captureFrame} disabled={!cameraOn || capturing}>
          {capturing ? "Processing..." : "Capture Frame"}
        </button>
      </div>

      <div className="mb-4" style={{ maxWidth: 480 }}>
        <video ref={videoRef} autoPlay playsInline className="w-100 rounded border" />
      </div>

      {results !== null && (
        <>
          <h5>Result</h5>
          {results.length === 0 ? (
            <p className="text-muted">No faces detected in that frame.</p>
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
        </>
      )}
    </div>
  );
}