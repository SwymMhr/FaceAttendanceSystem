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
