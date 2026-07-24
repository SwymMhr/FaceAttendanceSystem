import { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import {
  getBatches,
  getSubjects,
  getUsers,
  getBatchPeriodSlots,
  deletePeriodSlot,
  getBatchTimetable,
  createPeriod,
  deletePeriod,
} from "../api";
import PageHeader from "../components/PageHeader";

const DAYS = ["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"];

const emptyForm = { subject_id: "", teacher_id: "", day_of_week: "SUNDAY", period_number: "" };

export default function AdminSchedule() {
  const [searchParams, setSearchParams] = useSearchParams();

  const [batches, setBatches] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [slots, setSlots] = useState([]);

  // Batch selection lives in the URL (?batch=id) so links from/to the
  // Add Period page round-trip back to the same batch.
  const selectedBatchId = searchParams.get("batch") || "";
  const setSelectedBatchId = (id) => setSearchParams(id ? { batch: id } : {});

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
        const [batchData, subjectData, teacherData] = await Promise.all([
          getBatches(),
          getSubjects(),
          getUsers("teacher"),
        ]);
        setBatches(batchData);
        setSubjects(subjectData);
        setTeachers(teacherData);
        if (!selectedBatchId && batchData.length > 0) {
          setSelectedBatchId(String(batchData[0].id));
        }
      } catch (err) {
        setError(err.response?.data?.detail || "Failed to load reference data.");
      } finally {
        setLoading(false);
      }
    };
    loadRefData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Slots and the timetable are both scoped to whichever batch is selected —
  // refetch both whenever it changes.
  const fetchSlotsAndTimetable = async (batchId) => {
    if (!batchId) return;
    try {
      const [slotData, timetableData] = await Promise.all([
        getBatchPeriodSlots(batchId),
        getBatchTimetable(batchId),
      ]);
      setSlots(slotData);
      setTimetable(timetableData);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load this batch's schedule.");
    }
  };

  useEffect(() => {
    fetchSlotsAndTimetable(selectedBatchId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      await fetchSlotsAndTimetable(selectedBatchId);
    } catch (err) {
      // Conflict (409) or validation errors surface here, e.g. "This batch
      // already has 'X' in that slot" or "This teacher is already
      // teaching... which overlaps this slot".
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
      await fetchSlotsAndTimetable(selectedBatchId);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to remove period.");
    }
  };

  const handleDeleteSlot = async (slot) => {
    const inUse = timetable.some((p) => p.period_number === slot.period_number);
    const warning = inUse
      ? `Period #${slot.period_number} (${slot.start_time}\u2013${slot.end_time}) has classes assigned across the week. Removing it will also remove ALL of those. Continue?`
      : `Remove period #${slot.period_number} (${slot.start_time}\u2013${slot.end_time})?`;
    if (!window.confirm(warning)) return;

    setError("");
    try {
      await deletePeriodSlot(slot.id);
      await fetchSlotsAndTimetable(selectedBatchId);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to remove period slot.");
    }
  };

  if (loading) return <div className="page"><div className="page-loading">Loading...</div></div>;

  return (
    <div className="page">
      <PageHeader title="Manage Schedule" />

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="panel d-flex align-items-center gap-2 flex-wrap">
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

        {selectedBatchId && (
          <Link
            to={`/admin/schedule/add-period?batch=${selectedBatchId}`}
            className="btn btn-primary ms-auto"
          >
            + Add Period
          </Link>
        )}
      </div>

      {selectedBatchId && (
        <>
          <div className="panel">
          {slots.length === 0 ? (
            <div className="empty-state">
              This batch has no period times yet. Click <strong>+ Add Period</strong> above to create its first one.
            </div>
          ) : (
          <div className="table-responsive">
            <table className="table table-bordered text-center align-middle mb-0">
              <thead>
                <tr>
                  <th style={{ width: 150 }}>Period</th>
                  {DAYS.map((d) => (
                    <th key={d}>{d[0] + d.slice(1).toLowerCase()}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {slots.map((slot) => (
                  <tr key={slot.id}>
                    <td>
                      <div>#{slot.period_number}</div>
                      <small className="text-muted d-block">
                        {slot.start_time}–{slot.end_time}
                      </small>
                      <button
                        className="btn btn-sm btn-link text-danger p-0"
                        onClick={() => handleDeleteSlot(slot)}
                      >
                        Remove slot
                      </button>
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
          )}
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