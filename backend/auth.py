import re
from datetime import datetime, timedelta, timezone
from typing import Generator

import bcrypt
import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from config import JWT_EXPIRE_MINUTES, JWT_SECRET
from db import User, engine


router = APIRouter(prefix="/auth", tags=["auth"])
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_token(user: User) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user.id), "exp": expires_at}, JWT_SECRET, algorithm="HS256")


def _public_user(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "created_at": user.created_at,
    }


def _validate_credentials(name: str | None, email: str, password: str) -> tuple[str, str]:
    normalized_email = email.strip().lower()
    if not EMAIL_PATTERN.fullmatch(normalized_email):
        raise HTTPException(status_code=422, detail="Enter a valid email address")
    if len(password) < 6:
        raise HTTPException(status_code=422, detail="Password must be at least 6 characters")
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(status_code=422, detail="Password must be 72 bytes or fewer")
    normalized_name = (name or "").strip()
    if name is not None and not normalized_name:
        raise HTTPException(status_code=422, detail="Name cannot be empty")
    return normalized_name, normalized_email


def get_current_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[7:].strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return user


@router.post("/signup")
def signup(request: SignupRequest, session: Session = Depends(get_session)) -> dict:
    name, email = _validate_credentials(request.name, request.email, request.password)
    if session.exec(select(User).where(User.email == email)).first() is not None:
        raise HTTPException(status_code=409, detail="email already registered")
    user = User(name=name, email=email, password_hash=hash_password(request.password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="email already registered") from error
    session.refresh(user)
    return {"token": create_token(user), "user": _public_user(user)}


@router.post("/login")
def login(request: LoginRequest, session: Session = Depends(get_session)) -> dict:
    _, email = _validate_credentials(None, request.email, request.password)
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="wrong email or password")
    return {"token": create_token(user), "user": _public_user(user)}


@router.get("/me")
def get_me(user: User = Depends(get_current_user)) -> dict:
    return _public_user(user)