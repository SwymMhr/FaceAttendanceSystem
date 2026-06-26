import { useState } from "react";
import API from "../api";

export default function EnrollPage() {
  const [name, setName] = useState("");
  const [studentId, setStudentId] = useState("");
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setLoading(true);
    const formData = new FormData();
    formData.append("student_name", name);
    formData.append("student_id", studentId);

    for (let img of images) {
      formData.append("images", img);
    }

    try {
      const res = await API.post("/enroll_student", formData);
      alert(res.data.message);
    } catch (err) {
      alert("Enrollment failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="container mt-4">
        <div className="card">
          <div className="card-body">

            <h1>Enroll Student</h1>

            <input className="form-control mb-3" type="text" placeholder="Name"  onChange={(e) => setName(e.target.value)} />

            <input className="form-control mb-3" type="text" placeholder="Student ID" onChange={(e) => setStudentId(e.target.value)} />

            <input className="form-control mb-3" type="file" multiple onChange={(e) => setImages(Array.from(e.target.files))} />

            <div className="mt-2">
              {images.length > 0 && (
                <>
                  <strong>Selected Images:</strong>
                  <ul className="list-group mt-2">
                    {images.map((img, i) => (
                      <li key={i} className="list-group-item">
                        {img.name}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>

            <button className="btn btn-primary" onClick={handleSubmit} disabled={loading}>{loading ? "Enrolling..." : "Enroll"}</button>

          </div>
        </div>
      </div>
    </div>
  );
}