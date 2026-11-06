from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.models.login_attempt import LoginAttempt


def check_login_rate_limit(request: Request, email: str, db: Session) -> None:
    """Enforce database-backed brute force rate limit: max 5 failures per 15 minutes."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)

    recent_failures = db.query(LoginAttempt).filter(
        LoginAttempt.ip_address == client_ip,
        LoginAttempt.attempt_time >= cutoff,
        LoginAttempt.is_success == False
    ).count()

    if recent_failures >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again after 15 minutes."
        )


def verify_csrf_token(request: Request) -> None:
    """Verify CSRF token for state-changing requests."""
    # Only verify on state-changing methods
    if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        # Allow initial login and logout without prior CSRF
        if request.url.path in ["/api/v1/auth/login", "/api/v1/auth/logout"]:
            return
        
        cookie_csrf = request.cookies.get("csrf_token")
        header_csrf = request.headers.get("X-CSRF-Token")

        if not cookie_csrf or not header_csrf or cookie_csrf != header_csrf:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF validation failed: Missing or invalid CSRF token."
            )


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """Extract and validate current authenticated user from HttpOnly cookie or Bearer header."""
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in."
        )

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token."
        )

    user = db.query(User).filter(User.email == payload["sub"]).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found."
        )

    return user


def require_role(allowed_roles: List[str]):
    """Enforce API-level RBAC role authorization."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Action requires one of roles {allowed_roles}, but your role is '{current_user.role}'."
            )
        return current_user
    return role_checker
