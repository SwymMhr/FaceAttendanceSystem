# app/api/deps.py
# Shared FastAPI dependencies for authentication and role-based access control.
# Use these on any route that needs a logged-in user, or a specific role.

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.db_models import User
from app.core.security import decode_access_token

# tokenUrl is just for the interactive /docs page's "Authorize" button;
# the frontend calls POST /login directly and stores the token itself.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Decodes the Bearer token, looks up the user, and returns it.
    Raises 401 if the token is missing/invalid/expired, or the user
    no longer exists / has been deactivated.
    """
    credentials_error = HTTPException(
        status_code=401,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_error

    user_name = payload.get("sub")
    if user_name is None:
        raise credentials_error

    user = db.query(User).filter(User.user_name == user_name).first()
    if user is None or not user.is_active:
        raise credentials_error

    return user


def require_role(*allowed_roles: str):
    """
    Dependency factory for role-gating a route.

    Usage:
        @router.get("/admin/users")
        def list_users(current_user: User = Depends(require_role("admin"))):
            ...

        @router.get("/classes")
        def my_classes(current_user: User = Depends(require_role("teacher", "admin"))):
            ...
    """
    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"This action requires one of these roles: {', '.join(allowed_roles)}.",
            )
        return current_user

    return _check