# app/api/auth.py
# POST /login — verify credentials, return a JWT access token (with role).
# There is no /register anymore — admin creates all accounts directly.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.db.database import get_db
from app.models.db_models import User
from app.core.security import verify_password, create_access_token

router = APIRouter()


# ── Request/response schemas ──────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str
    # What the topbar/sidebar shows next to the avatar: the student/teacher's
    # full name where we have one, falling back to email for the rare case
    # a teacher/admin account was created without one.
    display_name: str
    role: str


# ── POST /login ────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated.")

    if user.student_profile:
        display_name = user.student_profile.student_name
    else:
        display_name = user.full_name or user.email

    token = create_access_token({"sub": user.email, "role": user.role})
    return TokenResponse(
        access_token=token, email=user.email, display_name=display_name, role=user.role
    )
