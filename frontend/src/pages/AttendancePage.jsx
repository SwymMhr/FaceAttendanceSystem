import { useRef } from "react";
import API from "../api";

export default function AttendancePage() {
  const videoRef = useRef(null);

  const startCamera = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    videoRef.current.srcObject = stream;
  };

  const captureFrame = async () => {
    const video = videoRef.current;

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0);

    canvas.toBlob(async (blob) => {
      const formData = new FormData();
      formData.append("image", blob, "frame.jpg");

      const res = await API.post("/process_frame", formData);
      console.log(res.data);
    }, "image/jpeg");
  };

  return (
    <div className="attendance-page">

      <h1 className="page-title">Live Attendance</h1>

      <div className="camera-controls">
        <button className="btn btn-primary" onClick={startCamera}>
          Start Camera
        </button>

        <button className="btn btn-success" onClick={captureFrame}>
          Capture Frame
        </button>
      </div>

      <div className="video-container">
        <video ref={videoRef} autoPlay playsInline />
      </div>

    </div>
  );
}