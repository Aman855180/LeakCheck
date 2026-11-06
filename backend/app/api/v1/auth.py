from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_password, create_access_token, generate_csrf_token
from app.api.deps import check_login_rate_limit, get_current_user
from app.models.user import User
from app.models.login_attempt import LoginAttempt
from app.schemas.auth import LoginRequest, TokenResponse, UserOut, MessageResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(
    login_data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    client_ip = request.client.host if request.client else "127.0.0.1"

    # 1. Enforce distributed rate limit
    check_login_rate_limit(request, login_data.email, db)

    # 2. Look up user
    user = db.query(User).filter(User.email == login_data.email).first()
    is_valid = user is not None and verify_password(login_data.password, user.password_hash)

    # 3. Log attempt
    attempt = LoginAttempt(
        ip_address=client_ip,
        email=login_data.email,
        attempt_time=datetime.now(timezone.utc),
        is_success=is_valid
    )
    db.add(attempt)
    db.commit()

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    # 4. Generate tokens
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role, "user_id": str(user.id)}
    )
    csrf_token = generate_csrf_token()

    # 5. Set HttpOnly cookie for JWT & readable cookie for CSRF
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=False,  # Set True in production over HTTPS
        max_age=3600 * 24
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,  # Frontend reads this to send X-CSRF-Token header
        samesite="lax",
        secure=False,
        max_age=3600 * 24
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        csrf_token=csrf_token,
        user=UserOut.model_validate(user)
    )


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response):
    response.delete_cookie(key="access_token", httponly=True, samesite="lax")
    response.delete_cookie(key="csrf_token", httponly=False, samesite="lax")
    return MessageResponse(message="Successfully signed out.")


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)
