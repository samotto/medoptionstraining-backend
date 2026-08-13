from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user, hash_password
from app.database import get_db
from app.models import Course, CourseLesson, Lesson, LessonCompletion, LookupList, LookupListItem, User, UserCourse
from app.schemas import (
    MessageResponse,
    PasswordResetRequest,
    UserCreate,
    UserMeResponse,
    UserProfileUpdate,
    UserResponse,
    UserUpdate,
)


router = APIRouter(prefix="/users", tags=["users"])


def require_admin(user: User) -> None:
    if user.role != "Admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


@router.get("", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UserResponse]:
    require_admin(current_user)
    users = db.query(User).order_by(User.email.asc()).all()
    return [UserResponse.model_validate(user) for user in users]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    require_admin(current_user)

    email = str(payload.email).strip().lower()
    name = (payload.name or email.split("@", 1)[0]).strip()
    if db.query(User).filter(func.lower(User.email) == email.lower()).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists")
    if db.query(User).filter(func.lower(User.name) == name.lower()).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this name already exists")

    now = datetime.now(timezone.utc)
    user = User(
        name=name,
        email=email,
        role=payload.role,
        password_hash=hash_password(payload.password),
        create_time=now,
        update_time=now,
        create_id=current_user.id,
        update_id=current_user.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.put("/me", response_model=UserMeResponse)
def update_current_user(
    payload: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserMeResponse:
    email = str(payload.email).strip().lower()
    name = payload.name.strip()
    duplicate_email = (
        db.query(User)
        .filter(func.lower(User.email) == email.lower(), User.id != current_user.id)
        .first()
    )
    if duplicate_email:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists")
    duplicate_name = (
        db.query(User)
        .filter(func.lower(User.name) == name.lower(), User.id != current_user.id)
        .first()
    )
    if duplicate_name:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this name already exists")

    current_user.name = name
    current_user.email = email
    current_user.update_time = datetime.now(timezone.utc)
    current_user.update_id = current_user.id
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return UserMeResponse.model_validate(current_user)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    require_admin(current_user)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    email = str(payload.email).strip().lower()
    name = payload.name.strip()
    duplicate_email = db.query(User).filter(func.lower(User.email) == email.lower(), User.id != user_id).first()
    if duplicate_email:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists")
    duplicate_name = db.query(User).filter(func.lower(User.name) == name.lower(), User.id != user_id).first()
    if duplicate_name:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this name already exists")

    user.name = name
    user.email = email
    user.role = payload.role
    user.update_time = datetime.now(timezone.utc)
    user.update_id = current_user.id
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", response_model=MessageResponse)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    require_admin(current_user)
    if current_user.id == user_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You cannot delete your own account")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Keep audit foreign keys valid after the user is removed. Assignment and
    # completion rows owned by this user are removed by their ON DELETE rules.
    for model in (Course, Lesson, CourseLesson, UserCourse, LessonCompletion):
        db.query(model).filter(model.create_id == user_id).update(
            {model.create_id: current_user.id}, synchronize_session=False
        )
        db.query(model).filter(model.update_id == user_id).update(
            {model.update_id: current_user.id}, synchronize_session=False
        )
    db.query(LookupList).filter(LookupList.create_id == user_id).update(
        {LookupList.create_id: current_user.id}, synchronize_session=False
    )
    db.query(LookupList).filter(LookupList.update_id == user_id).update(
        {LookupList.update_id: current_user.id}, synchronize_session=False
    )
    db.query(LookupListItem).filter(LookupListItem.create_id == user_id).update(
        {LookupListItem.create_id: current_user.id}, synchronize_session=False
    )
    db.query(LookupListItem).filter(LookupListItem.update_id == user_id).update(
        {LookupListItem.update_id: current_user.id}, synchronize_session=False
    )
    db.query(User).filter(User.create_id == user_id).update(
        {User.create_id: current_user.id}, synchronize_session=False
    )
    db.query(User).filter(User.update_id == user_id).update(
        {User.update_id: current_user.id}, synchronize_session=False
    )
    db.delete(user)
    db.commit()
    return MessageResponse(message="user deleted")


@router.post("/{user_id}/reset-password", response_model=MessageResponse)
def reset_password(
    user_id: int,
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    if current_user.id != user_id and current_user.role != "Admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot reset this user's password")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.password_hash = hash_password(payload.new_password)
    user.update_time = datetime.now(timezone.utc)
    user.update_id = current_user.id
    db.add(user)
    db.commit()
    return MessageResponse(message="password updated")
