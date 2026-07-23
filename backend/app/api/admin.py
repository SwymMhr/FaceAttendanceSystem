# app/api/admin.py
# Admin-only endpoints: manage batches, subjects, and user accounts
# (students + teachers). Every route requires role == "admin".

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, EmailStr
from typing import Optional, List

from app.db.database import get_db
from app.models.db_models import User, Batch, Student, Subject
from app.core.security import hash_password
from app.api.deps import require_role

router = APIRouter(prefix="/admin", dependencies=[Depends(require_role("admin"))])


def _display_name(user: User, student: Optional[Student] = None) -> str:
    """The name UserOut reports: student's name if this is a student
    account, else the teacher/admin's full_name, falling back to email
    if that was somehow never set."""
    student = student if student is not None else user.student_profile
    if student:
        return student.student_name
    return user.full_name or user.email


# ══════════════════════════════════════════════════════════════════════════
# Schemas
# ══════════════════════════════════════════════════════════════════════════

class BatchCreate(BaseModel):
    batch_name: str


class BatchOut(BaseModel):
    id: int
    batch_name: str

    class Config:
        from_attributes = True


class SubjectCreate(BaseModel):
    subject_code: str
    subject_name: str


class SubjectOut(BaseModel):
    id: int
    subject_code: str
    subject_name: str

    class Config:
        from_attributes = True


class TeacherCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str


class StudentCreate(BaseModel):
    email: EmailStr
    password: str
    student_code: str
    student_name: str
    batch_id: Optional[int] = None


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None        # leave unset to keep the current password
    is_active: Optional[bool] = None
    role: Optional[str] = None            # promote/demote: "student" | "teacher" | "admin"
    full_name: Optional[str] = None       # only meaningful for teacher/admin accounts
    student_code: Optional[str] = None    # only meaningful if this user has a student profile
    student_name: Optional[str] = None    # only meaningful if this user has a student profile
    batch_id: Optional[int] = None        # only meaningful if this user has a student profile


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    # Student's full name if this is a student account, otherwise the
    # teacher/admin's full_name (or email, if that was never set) — this
    # is what the UI shows for "who this account belongs to".
    full_name: str
    # tbl_students.id — NOT the same as `id` above (which is tbl_users.id).
    # Anything that keys off the student record itself (face embeddings,
    # attendance, roster lookups) needs THIS id, not the login account id.
    student_db_id: Optional[int] = None
    student_code: Optional[str] = None
    student_name: Optional[str] = None
    batch_id: Optional[int] = None
    batch_name: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════
# Batches
# ══════════════════════════════════════════════════════════════════════════

@router.post("/batches", response_model=BatchOut)
def create_batch(payload: BatchCreate, db: Session = Depends(get_db)):
    if db.query(Batch).filter(Batch.batch_name == payload.batch_name).first():
        raise HTTPException(status_code=400, detail="A batch with this name already exists.")

    batch = Batch(batch_name=payload.batch_name)
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/batches", response_model=List[BatchOut])
def list_batches(db: Session = Depends(get_db)):
    return db.query(Batch).order_by(Batch.batch_name).all()


@router.put("/batches/{batch_id}", response_model=BatchOut)
def update_batch(batch_id: int, payload: BatchCreate, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found.")

    batch.batch_name = payload.batch_name
    db.commit()
    db.refresh(batch)
    return batch


@router.delete("/batches/{batch_id}")
def delete_batch(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found.")

    # Students in this batch aren't deleted — their batch_id just goes null
    # (ON DELETE SET NULL). Periods for this batch ARE deleted (CASCADE).
    db.delete(batch)
    db.commit()
    return {"message": f"Batch '{batch.batch_name}' deleted."}


# ══════════════════════════════════════════════════════════════════════════
# Subjects
# ══════════════════════════════════════════════════════════════════════════

@router.post("/subjects", response_model=SubjectOut)
def create_subject(payload: SubjectCreate, db: Session = Depends(get_db)):
    if db.query(Subject).filter(Subject.subject_code == payload.subject_code).first():
        raise HTTPException(status_code=400, detail="A subject with this code already exists.")
    if db.query(Subject).filter(Subject.subject_name == payload.subject_name).first():
        raise HTTPException(status_code=400, detail="A subject with this name already exists.")

    subject = Subject(subject_code=payload.subject_code, subject_name=payload.subject_name)
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject


@router.get("/subjects", response_model=List[SubjectOut])
def list_subjects(db: Session = Depends(get_db)):
    return db.query(Subject).order_by(Subject.subject_code).all()


@router.put("/subjects/{subject_id}", response_model=SubjectOut)
def update_subject(subject_id: int, payload: SubjectCreate, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    subject.subject_code = payload.subject_code
    subject.subject_name = payload.subject_name
    db.commit()
    db.refresh(subject)
    return subject


@router.delete("/subjects/{subject_id}")
def delete_subject(subject_id: int, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    db.delete(subject)
    db.commit()
    return {"message": f"Subject '{subject.subject_name}' deleted."}


# ══════════════════════════════════════════════════════════════════════════
# Users — teachers
# ══════════════════════════════════════════════════════════════════════════

@router.post("/users/teachers", response_model=UserOut)
def create_teacher(payload: TeacherCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="That email is already registered.")

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="teacher",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserOut(
        id=user.id, email=user.email, full_name=_display_name(user),
        role=user.role, is_active=user.is_active,
    )


# ══════════════════════════════════════════════════════════════════════════
# Users — students
# ══════════════════════════════════════════════════════════════════════════

@router.post("/users/students", response_model=UserOut)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="That email is already registered.")
    if db.query(Student).filter(Student.student_code == payload.student_code).first():
        raise HTTPException(status_code=400, detail="That student code is already in use.")

    if payload.batch_id is not None:
        if not db.query(Batch).filter(Batch.id == payload.batch_id).first():
            raise HTTPException(status_code=404, detail="Batch not found.")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="student",
    )
    db.add(user)
    db.flush()  # get user.id before commit

    student = Student(
        student_code=payload.student_code,
        student_name=payload.student_name,
        user_id=user.id,
        batch_id=payload.batch_id,
    )
    db.add(student)
    db.commit()
    db.refresh(user)
    db.refresh(student)

    return UserOut(
        id=user.id, email=user.email, full_name=_display_name(user, student),
        role=user.role, is_active=user.is_active,
        student_db_id=student.id,
        student_code=student.student_code, student_name=student.student_name,
        batch_id=student.batch_id,
        batch_name=student.batch.batch_name if student.batch else None,
    )


# ══════════════════════════════════════════════════════════════════════════
# Users — list / update / delete (any role)
# ══════════════════════════════════════════════════════════════════════════

@router.get("/users", response_model=List[UserOut])
def list_users(role: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    users = query.order_by(User.email).all()

    out = []
    for u in users:
        sp = u.student_profile
        out.append(UserOut(
            id=u.id, email=u.email, full_name=_display_name(u, sp),
            role=u.role, is_active=u.is_active,
            student_db_id=sp.id if sp else None,
            student_code=sp.student_code if sp else None,
            student_name=sp.student_name if sp else None,
            batch_id=sp.batch_id if sp else None,
            batch_name=sp.batch.batch_name if (sp and sp.batch) else None,
        ))
    return out


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    sp = user.student_profile
    return UserOut(
        id=user.id, email=user.email, full_name=_display_name(user, sp),
        role=user.role, is_active=user.is_active,
        student_db_id=sp.id if sp else None,
        student_code=sp.student_code if sp else None,
        student_name=sp.student_name if sp else None,
        batch_id=sp.batch_id if sp else None,
        batch_name=sp.batch.batch_name if (sp and sp.batch) else None,
    )


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if payload.email is not None:
        user.email = payload.email
    if payload.password:
        user.password_hash = hash_password(payload.password)
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.role is not None:
        if payload.role not in ("student", "teacher", "admin"):
            raise HTTPException(status_code=400, detail="Role must be student, teacher, or admin.")
        user.role = payload.role
    if payload.full_name is not None:
        user.full_name = payload.full_name

    sp = user.student_profile
    if sp:
        if payload.student_code is not None and payload.student_code != sp.student_code:
            taken = (
                db.query(Student)
                  .filter(Student.student_code == payload.student_code, Student.id != sp.id)
                  .first()
            )
            if taken:
                raise HTTPException(status_code=400, detail="That student code is already in use.")
            sp.student_code = payload.student_code
        if payload.student_name is not None:
            sp.student_name = payload.student_name
        # Use fields_set (not "is not None") so batch_id=null can explicitly
        # clear a student's batch, distinct from the field being omitted.
        if "batch_id" in payload.model_fields_set:
            if payload.batch_id is not None and not db.query(Batch).filter(Batch.id == payload.batch_id).first():
                raise HTTPException(status_code=404, detail="Batch not found.")
            sp.batch_id = payload.batch_id

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="That email is already in use.")

    db.refresh(user)

    return UserOut(
        id=user.id, email=user.email, full_name=_display_name(user, sp),
        role=user.role, is_active=user.is_active,
        student_db_id=sp.id if sp else None,
        student_code=sp.student_code if sp else None,
        student_name=sp.student_name if sp else None,
        batch_id=sp.batch_id if sp else None,
        batch_name=sp.batch.batch_name if (sp and sp.batch) else None,
    )


@router.delete("/users/{user_id}")
def delete_user(user_id: int, current_user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You can't delete your own account.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Deleting the User row alone would only null out the student's user_id
    # (ON DELETE SET NULL) and leave an orphaned student profile behind —
    # explicitly delete it too, which cascades to embeddings/attendance.
    if user.student_profile:
        db.delete(user.student_profile)

    db.delete(user)
    db.commit()
    return {"message": f"User '{user.email}' deleted."}