# app/api/auth.py
# POST /login — verify credentials, return a JWT access token (with role).
# There is no /register anymore — admin creates all accounts directly.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel

from app.db.database import get_db
from app.models.db_models import User
from app.core.security import verify_password, create_access_token

router = APIRouter()


# ── Request/response schemas ──────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str  # accepts user_name OR email
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


# ── POST /login ────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = (
        db.query(User)
        .filter(or_(User.user_name == payload.username, User.email == payload.username))
        .first()
    )

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated.")

    token = create_access_token({"sub": user.user_name, "role": user.role})
    return TokenResponse(access_token=token, username=user.user_name, role=user.role)