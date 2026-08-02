# Backend admin/maintenance scripts (PowerShell)

Convenience wrappers for the long one-off commands you otherwise have to type
by hand. Run them from anywhere in the repo; each script `cd`s to `backend\`
itself so `app.*` imports and `backend\.env` resolve correctly.

## First run: allow scripts

Your PowerShell execution policy is currently Restricted, so `.ps1` files
won't run until you relax it (one time, per user):

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Or, without changing the policy, launch each script with a one-off bypass:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\create-admin.ps1
```

## Quick reference

| Script | What it does | Destructive? |
|---|---|---|
| `fresh-start.ps1` | Wipe DB + recreate schema + create fresh admin | YES |
| `fullwipe.ps1` | Drop and recreate the schema (all data lost) | YES |
| `truncate.ps1` | Delete all rows, keep the schema (ids restart) | YES |
| `clear-attendance.ps1` | Delete attendance history only | Partial |
| `create-admin.ps1` | Bootstrap the first admin (idempotent) | No |
| `send-test-email.ps1` | Send a test absence email via SMTP settings | No |
| `create-batch.ps1` | Create a batch (API, backend must run) | No |
| `create-subject.ps1` | Create a subject (API, backend must run) | No |
| `create-teacher.ps1` | Create a teacher account (API) | No |
| `create-student.ps1` | Create a student account (API) | No |
| `create-slot.ps1` | Add a period time-slot to a batch (API) | No |
| `create-period.ps1` | Put a subject+teacher into a slot (API) | No |
| `run-tests.ps1` | Run `test_db.py`, `test_cctv_service.py`, `test_model.py` | No |

## Examples

```powershell
# Wipe everything and create a fresh admin:
.\scripts\fresh-start.ps1

# Just clear the attendance history:
.\scripts\clear-attendance.ps1

# First admin with custom credentials:
.\scripts\create-admin.ps1 -Email me@example.com -Password secret -Name "My Name"

# SMTP test (reads SMTP_* from backend\.env):
.\scripts\send-test-email.ps1 -To me@example.com -StudentName "Ada" -SubjectName IT

# Set up a timetable (run the backend first):
.\scripts\create-batch.ps1 -BatchName "2024 Software"
.\scripts\create-subject.ps1 -SubjectCode IT -SubjectName "Information Technology"
.\scripts\create-teacher.ps1 -FullName "Jane Doe" -Email jane@example.com -Password secret
.\scripts\create-student.ps1 -Email ada@example.com -Password secret -StudentCode 2024IT001 -StudentName "Ada Lovelace" -BatchId 1
.\scripts\create-slot.ps1 -BatchId 1 -StartTime "09:00" -EndTime "09:50"
.\scripts\create-period.ps1 -BatchId 1 -SubjectId 1 -TeacherId 1 -Day MONDAY -PeriodNumber 1
```

## Notes

- The destructive scripts (`fullwipe`, `truncate`, `clear-attendance`,
  `fresh-start`) touch the database directly via SQLAlchemy and do NOT require
  the backend to be running. **Do not run them while uvicorn is up** if you
  want to avoid locked/wiped-in-the-middle state.
- The `create-*.ps1` API scripts call the running backend at `http://127.0.0.1:8000`
  and log in as the admin user. Start the backend first, and make sure the admin
  account exists (see `create-admin.ps1`).
- Python interpreter: scripts use `python` from PATH; set `$env:PYTHON` to a
  specific interpreter if needed.
- Admin login defaults: `admin@test.com` / `admin123`. Override via
  `$env:ADMIN_EMAIL` / `$env:ADMIN_PASSWORD` (or the script parameters).
- Secrets live in `backend\.env` (gitignored); the API scripts only use the
  admin login above and never embed credentials from `.env`.
- `create-student.ps1` with no `-BatchId` leaves the student unbatched.
  `day_of_week` for `create-period.ps1` must be one of
  SUNDAY..FRIDAY (Saturday is the weekend).
