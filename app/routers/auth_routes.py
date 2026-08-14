from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    create_email_verification_token,
    create_password_reset_token,
    decode_password_reset_token,
    decode_email_verification_token,
    get_current_user,
    hash_password,
    password_reset_token_matches,
    verify_password,
)
from app.config import get_settings
from app.database import get_db
from app.email_service import EmailDeliveryError, send_password_reset_email, send_verification_email
from app.models import User
from app.schemas import (
    EmailVerificationRequest,
    CompletePasswordResetRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegistrationResponse,
    RegisterRequest,
    ResendVerificationRequest,
    UserLoginResponse,
    UserMeResponse,
)


router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def set_auth_cookie(response: Response, user_id: int) -> None:
    token = create_access_token(subject=str(user_id))
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )


@router.post("/login", response_model=UserLoginResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> UserLoginResponse:
    email = str(payload.email).strip().lower()
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if user.role == "Pending":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email address has not been verified")

    user.last_logon_time = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)

    set_auth_cookie(response, user.id)

    return UserLoginResponse.model_validate(user)


@router.post("/register", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> RegistrationResponse:
    email = str(payload.email).strip().lower()
    name = (payload.name or email.split("@", 1)[0]).strip()
    if db.query(User).filter(func.lower(User.email) == email.lower()).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    if db.query(User).filter(func.lower(User.name) == name.lower()).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this name already exists")

    now = datetime.now(timezone.utc)
    user = User(
        name=name,
        email=email,
        role="Pending",
        password_hash=hash_password(payload.password),
        create_time=now,
        update_time=now,
        last_logon_time=None,
    )
    db.add(user)
    db.flush()
    user.create_id = user.id
    user.update_id = user.id
    db.commit()
    db.refresh(user)
    token = create_email_verification_token(user.id, user.email)
    try:
        send_verification_email(user.email, token)
    except EmailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Account created, but the verification email could not be sent. Please resend it.",
        ) from exc
    return RegistrationResponse(message="Verification email sent", email=user.email)


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(
    payload: EmailVerificationRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> MessageResponse:
    user_id, token_email = decode_email_verification_token(payload.token)
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.email.strip().lower() != token_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The verification link is invalid")
    if user.role != "Pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This email address is already verified")

    user.role = "Basic"
    user.update_time = datetime.now(timezone.utc)
    user.update_id = user.id
    db.add(user)
    db.commit()
    response.delete_cookie(
        key="access_token",
        path="/",
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    return MessageResponse(message="Email verified. Please log in.")


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(
    payload: ResendVerificationRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    email = str(payload.email).strip().lower()
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if user and user.role == "Pending":
        token = create_email_verification_token(user.id, user.email)
        try:
            send_verification_email(user.email, token)
        except EmailDeliveryError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The verification email could not be sent. Please try again.",
            ) from exc
    return MessageResponse(message="If this account is pending, a verification email has been sent")


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    email = str(payload.email).strip().lower()
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if user:
        token = create_password_reset_token(user.id, user.email, user.password_hash)
        try:
            send_password_reset_email(user.email, token)
        except EmailDeliveryError:
            # Preserve the same response for known and unknown email addresses.
            pass
    return MessageResponse(message="If an account exists for this email, a password reset link has been sent")


@router.post("/reset-password", response_model=MessageResponse)
def complete_password_reset(
    payload: CompletePasswordResetRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    user_id, token_email, password_version = decode_password_reset_token(payload.token)
    user = db.query(User).filter(User.id == user_id).first()
    if (
        not user
        or user.email.strip().lower() != token_email
        or not password_reset_token_matches(password_version, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The password reset link is invalid or has expired",
        )

    now = datetime.now(timezone.utc)
    user.password_hash = hash_password(payload.new_password)
    user.update_time = now
    user.update_id = user.id
    db.add(user)
    db.commit()
    return MessageResponse(message="Password updated")


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response) -> MessageResponse:
    response.delete_cookie(
        key="access_token",
        path="/",
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    return MessageResponse(message="logged out")


@router.get("/me", response_model=UserMeResponse)
def me(current_user: User = Depends(get_current_user)) -> UserMeResponse:
    return UserMeResponse.model_validate(current_user)
