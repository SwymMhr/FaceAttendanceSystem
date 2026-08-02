import { useEffect, useRef, useState } from "react";
import { getCctvStatus, getCctvEvents, toggleCctv, updateCctvSettings, getRole } from "../api";
import PageHeader from "../components/PageHeader";

const STATUS_BADGE = {
  pending: "bg-info text-dark",
  skipped: "bg-warning text-dark",
  error: "bg-danger",
  unrecognized: "bg-secondary",
  rejected: "bg-danger text-white",
};

const API_BASE_URL = "http://localhost:8000";

function ToggleBtn({ label, active, onClick }) {
  return (
    <button
      className={`btn btn-sm ${active ? "btn-success" : "btn-outline-secondary"}`}
      onClick={onClick}
    >
      {label}: {active ? "ON" : "OFF"}
    </button>
  );
}

export default function CCTVPage() {
  const [status, setStatus] = useState(null);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState("");
  const [streamKey, setStreamKey] = useState(0);
  const [captureMin, setCaptureMin] = useState("1");
  const [captureMax, setCaptureMax] = useState("5");
  const [saveMsg, setSaveMsg] = useState("");
  const intervalTouchedRef = useRef(false);
  const role = getRole();

  useEffect(() => {
    const load = () => {
      getCctvStatus()
        .then((s) => {
          setStatus(s);
          if (!intervalTouchedRef.current) {
            if (s.capture_min_interval != null) setCaptureMin(String(s.capture_min_interval));
            if (s.capture_max_interval != null) setCaptureMax(String(s.capture_max_interval));
          }
        })
        .catch((err) => setError(err.response?.data?.detail || "Failed to load CCTV status."));
      getCctvEvents(50)
        .then((d) => setEvents(d.events || []))
        .catch(() => {});
    };
    load();
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, []);

  const token = localStorage.getItem("token");
  const streamSrc = `${API_BASE_URL}/cctv/stream?token=${token}`;

  const handleToggle = async () => {
    try {
      const res = await toggleCctv();
      setStatus((s) => ({ ...s, running: res.running }));
      setStreamKey((k) => k + 1);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to toggle CCTV service.");
    }
  };

  const handleSetting = async (key, value) => {
    try {
      const res = await updateCctvSettings({ [key]: value });
      setStatus(res);
      setError("");
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to update setting.");
    }
  };

  const handleSaveInterval = async () => {
    setSaveMsg("");
    const min = parseFloat(captureMin);
    const max = parseFloat(captureMax);
    if (Number.isNaN(min) || Number.isNaN(max) || min <= 0 || max <= 0 || min > max) {
      setSaveMsg("Enter valid intervals (0 < min <= max).");
      return;
    }
    try {
      const res = await updateCctvSettings({ capture_min: min, capture_max: max });
      intervalTouchedRef.current = false;
      setStatus(res);
      setSaveMsg("Saved");
    } catch (err) {
      setSaveMsg(err.response?.data?.detail || "Save failed");
    }
  };

  const running = status?.running;

  return (
    <div className="page">
      <PageHeader
        title="CCTV Live View"
        subtitle="Automatic attendance from the classroom camera. Auto-capture runs only during scheduled class periods."
      />

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="panel">
        <div className="d-flex align-items-center gap-3 mb-3">
          <span className={`badge ${status?.connected ? "bg-success" : "bg-danger"}`}>
            {status?.connected ? "Connected" : "Disconnected"}
          </span>
          <span className="small text-muted">
            {status?.resolution || "—"} · Persons in frame: {status?.person_count ?? 0}
          </span>
          <span className={`badge ${status?.in_period ? "bg-success" : "bg-warning text-dark"}`}>
            {status?.in_period ? "In class period" : "Outside class period"}
          </span>
          {role === "admin" && (
            <button className="btn btn-sm btn-outline-secondary ms-auto" onClick={handleToggle}>
              {running ? "Stop" : "Start"}
            </button>
          )}
        </div>

        <div className="d-flex flex-wrap align-items-center gap-2 mb-3">
          <ToggleBtn
            label="Detect"
            active={!!status?.detect_enabled}
            onClick={() => handleSetting("detect", !status?.detect_enabled)}
          />
          <ToggleBtn
            label="Recognize"
            active={!!status?.recognize_enabled}
            onClick={() => handleSetting("recognize", !status?.recognize_enabled)}
          />
          {role === "admin" && (
            <ToggleBtn
              label="Auto Capture"
              active={!!status?.auto_capture_enabled}
              onClick={() => handleSetting("auto_capture", !status?.auto_capture_enabled)}
            />
          )}
        </div>

        {role === "admin" && (
          <div className="d-flex align-items-center gap-2 mb-3">
            <label className="small text-muted mb-0">Capture interval (s):</label>
            <input
              type="number" min="0.5" step="0.5" value={captureMin}
              onChange={(e) => { intervalTouchedRef.current = true; setSaveMsg(""); setCaptureMin(e.target.value); }}
              className="form-control form-control-sm" style={{ width: 90 }}
            />
            <span>–</span>
            <input
              type="number" min="0.5" step="0.5" value={captureMax}
              onChange={(e) => { intervalTouchedRef.current = true; setSaveMsg(""); setCaptureMax(e.target.value); }}
              className="form-control form-control-sm" style={{ width: 90 }}
            />
            <button className="btn btn-sm btn-primary" onClick={handleSaveInterval}>Save</button>
            {saveMsg && <span className="small text-muted">{saveMsg}</span>}
          </div>
        )}

        {!running && (
          <div className="alert alert-warning">
            CCTV service is not running. Check <code>CCTV_ENABLED</code> in backend/.env.
          </div>
        )}

        <div style={{ maxWidth: 720 }}>
          <img
            key={streamKey}
            src={streamSrc}
            alt="CCTV feed"
            className="w-100 rounded border bg-dark"
          />
        </div>
      </div>

      <div className="panel">
        <h2 className="panel-title">Recent Recognitions</h2>
        {events.length === 0 ? (
          <div className="empty-state">No detections yet.</div>
        ) : (
          <ul className="list-group" style={{ maxWidth: 640 }}>
            {events.map((e, i) => (
              <li key={i} className="list-group-item d-flex justify-content-between align-items-center">
                <div>
                  <span className="fw-bold">{e.name}</span>
                  <div className="small text-muted">{e.message}</div>
                </div>
                <div className="text-end">
                  <span className={`badge ${STATUS_BADGE[e.status] || "bg-secondary"}`}>{e.status}</span>
                  <div className="small text-muted">
                    {e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : ""}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
