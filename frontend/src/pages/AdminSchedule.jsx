import { useEffect, useState } from "react";
import {
  getBatches,
  getSubjects,
  getUsers,
  getPeriodSlots,
  getBatchTimetable,
  createPeriod,
  deletePeriod,
} from "../api";
import PageHeader from "../components/PageHeader";

const DAYS = ["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY"];

const emptyForm = { subject_id: "", teacher_id: "", day_of_week: "SUNDAY", period_number: "" };

export default function AdminSchedule() {
  const [batches, setBatches] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [slots, setSlots] = useState([]);

  const [selectedBatchId, setSelectedBatchId] = useState("");
  const [timetable, setTimetable] = useState([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  // Load reference data once.
  useEffect(() => {
    const loadRefData = async () => {
      try {
        const [batchData, subjectData, teacherData, slotData] = await Promise.all([
          getBatches(),
          getSubjects(),
          getUsers("teacher"),
          getPeriodSlots(),
        ]);
        setBatches(batchData);
        setSubjects(subjectData);
        setTeachers(teacherData);
        setSlots(slotData);
        if (batchData.length > 0) setSelectedBatchId(String(batchData[0].id));
      } catch (err) {
        setError(err.response?.data?.detail || "Failed to load reference data.");
      } finally {
        setLoading(false);
      }
    };
    loadRefData();
  }, []);

  const fetchTimetable = async (batchId) => {
    if (!batchId) return;
    try {
      const data = await getBatchTimetable(batchId);
      setTimetable(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load timetable.");
    }
  };

  useEffect(() => {
    fetchTimetable(selectedBatchId);
  }, [selectedBatchId]);

  const cellFor = (day, periodNumber) =>
    timetable.find((p) => p.day_of_week === day && p.period_number === periodNumber);

  const openFormFor = (day, periodNumber) => {
    setForm({ subject_id: "", teacher_id: "", day_of_week: day, period_number: periodNumber });
    setShowForm(true);
    setError("");
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!selectedBatchId || !form.subject_id || !form.teacher_id || !form.period_number) return;

    setSaving(true);
    setError("");
    try {
      await createPeriod({
        batch_id: Number(selectedBatchId),
        subject_id: Number(form.subject_id),
        teacher_id: Number(form.teacher_id),
        day_of_week: form.day_of_week,
        period_number: Number(form.period_number),
      });
      setShowForm(false);
      setForm(emptyForm);
      await fetchTimetable(selectedBatchId);
    } catch (err) {
      // Conflict (409) or validation errors surface here, e.g. "This batch
      // already has 'X' in that slot" or "This teacher is already teaching...".
      setError(err.response?.data?.detail || "Failed to assign period.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (period) => {
    if (!window.confirm(`Remove ${period.subject_name} (${period.day_of_week}, period ${period.period_number}) from the timetable?`)) {
      return;
    }
    setError("");
    try {
      await deletePeriod(period.id);
      await fetchTimetable(selectedBatchId);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to remove period.");
    }
  };

  if (loading) return <div className="page"><div className="page-loading">Loading...</div></div>;

  return (
    <div className="page">
      <PageHeader title="Manage Schedule" />

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="panel d-flex align-items-center gap-2">
        <label className="mb-0">Batch:</label>
        <select
          className="form-select"
          style={{ maxWidth: 260 }}
          value={selectedBatchId}
          onChange={(e) => setSelectedBatchId(e.target.value)}
        >
          {batches.map((b) => (
            <option key={b.id} value={b.id}>
              {b.batch_name}
            </option>
          ))}
        </select>
        {batches.length === 0 && (
          <span className="text-muted">Create a batch first.</span>
        )}
      </div>

      {selectedBatchId && (
        <>
          <div className="panel">
          <div className="table-responsive">
            <table className="table table-bordered text-center align-middle mb-0">
              <thead>
                <tr>
                  <th style={{ width: 140 }}>Period</th>
                  {DAYS.map((d) => (
                    <th key={d}>{d[0] + d.slice(1).toLowerCase()}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {slots.map((slot) => (
                  <tr key={slot.period_number}>
                    <td>
                      <div>#{slot.period_number}</div>
                      <small className="text-muted">
                        {slot.start_time}–{slot.end_time}
                      </small>
                    </td>
                    {DAYS.map((day) => {
                      const period = cellFor(day, slot.period_number);
                      return (
                        <td key={day} style={{ minWidth: 150 }}>
                          {period ? (
                            <div>
                              <div className="fw-bold">{period.subject_code}</div>
                              <small className="text-muted d-block">{period.teacher_name}</small>
                              <button
                                className="btn btn-sm btn-outline-danger mt-1"
                                onClick={() => handleDelete(period)}
                              >
                                Remove
                              </button>
                            </div>
                          ) : (
                            <button
                              className="btn btn-sm btn-outline-secondary"
                              onClick={() => openFormFor(day, slot.period_number)}
                            >
                              + Assign
                            </button>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          </div>

          {showForm && (
            <div className="panel" style={{ maxWidth: 640 }}>
                <h2 className="panel-title">
                  Assign period — {form.day_of_week[0] + form.day_of_week.slice(1).toLowerCase()}, slot #{form.period_number}
                </h2>
                <form className="row g-2" onSubmit={handleCreate}>
                  <div className="col-md-6">
                    <select
                      className="form-select"
                      value={form.subject_id}
                      onChange={(e) => setForm({ ...form, subject_id: e.target.value })}
                      required
                    >
                      <option value="">Select subject...</option>
                      {subjects.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.subject_code} — {s.subject_name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="col-md-6">
                    <select
                      className="form-select"
                      value={form.teacher_id}
                      onChange={(e) => setForm({ ...form, teacher_id: e.target.value })}
                      required
                    >
                      <option value="">Select teacher...</option>
                      {teachers.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.full_name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="col-12 d-flex gap-2 mt-2">
                    <button className="btn btn-primary" type="submit" disabled={saving}>
                      {saving ? "Assigning..." : "Assign"}
                    </button>
                    <button
                      type="button"
                      className="btn btn-outline-secondary"
                      onClick={() => {
                        setShowForm(false);
                        setError("");
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </form>
            </div>
          )}
        </>
      )}
    </div>
  );
}