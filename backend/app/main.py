# app/main.py
# The FastAPI application entry point.
# Run this file with:  uvicorn app.main:app --reload

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.services.scheduler import start_scheduler
from app.api import enroll, attendance, realtime, auth, admin, schedule, dashboard, cctv
from app.services.cctv_service import cctv_service
from app.db.database import Base, engine

# ── Create all tables in PostgreSQL on startup ────────────────────────────────
# SQLAlchemy reads your db_models.py and creates any missing tables.
# Safe to run repeatedly — it skips tables that already exist.
Base.metadata.create_all(bind=engine)

# ── Create the FastAPI app ────────────────────────────────────────────────────
app = FastAPI(
    title       = "Face Recognition Attendance System",
    description = "API for student enrollment and live attendance tracking.",
    version     = "1.0.0",
)
start_scheduler()
cctv_service.start()

# ── CORS — allow your React frontend to call this backend ─────────────────────
# React dev server runs on http://localhost:5173 (Vite default).
# Without this, the browser will block all API calls from the frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["http://localhost:5173", "http://localhost:3000"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Register routes ───────────────────────────────────────────────────────────
app.include_router(auth.router,       tags=["Auth"])
app.include_router(enroll.router,     tags=["Enrollment"])
app.include_router(attendance.router, tags=["Attendance"])
app.include_router(realtime.router, tags=["Realtime"])
app.include_router(admin.router)
app.include_router(schedule.router)
app.include_router(cctv.router, tags=["CCTV"])

app.include_router(dashboard.student_router, tags=["Student Dashboard"])
app.include_router(dashboard.teacher_router, tags=["Teacher Dashboard"])
app.include_router(dashboard.admin_dashboard_router, tags=["Admin Dashboard"])

# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "Attendance API is running."}