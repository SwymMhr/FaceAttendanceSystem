# app/services/notify.py
# Sends the absence email. Wrapped in try/except so an SMTP failure never
# crashes the attendance-finalization job — it just logs and moves on.

import smtplib
from email.mime.text import MIMEText
from datetime import date as date_type

from app.core.config import settings


def send_absence_email(to_email: str, student_name: str, subject_name: str, on_date: date_type):
    subject = f"Absence recorded: {subject_name} on {on_date.isoformat()}"
    body = (
        f"Hi {student_name},\n\n"
        f"You were marked absent for {subject_name} on {on_date.isoformat()}.\n"
        f"If you believe this is a mistake, please contact your instructor.\n\n"
        f"— Attendance System"
    )

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to_email

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())
        print(f"[notify] Absence email sent to {to_email}")
    except Exception as e:
        # Don't let a broken SMTP config take down attendance processing.
        print(f"[notify] FAILED to send absence email to {to_email}: {e}")