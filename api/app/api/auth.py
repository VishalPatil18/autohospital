from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.core.config import settings
from app.db.models import Doctor, Patient, User
from app.db.schemas import LoginRequest, TokenResponse, UserCreate, UserResponse
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

_NOT_FOUND_OR_BAD_PASSWORD = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Incorrect email or password",
)


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=False,  # set True in production (HTTPS)
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, db: AsyncSession = Depends(get_db)) -> UserResponse:
    # Check for duplicate email
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with that email already exists.",
        )

    password_hash = get_password_hash(body.password)
    user = User(
        email=body.email,
        password_hash=password_hash,
        role=body.role,
    )
    db.add(user)
    await db.flush()  # populate user.id without committing

    if body.role == "patient":
        patient = Patient(
            user_id=user.id,
            first_name=body.first_name,
            last_name=body.last_name,
            dob=date(2000, 1, 1),  # placeholder — can be updated via PATCH later
        )
        db.add(patient)
    elif body.role == "doctor":
        doctor = Doctor(
            user_id=user.id,
            first_name=body.first_name,
            last_name=body.last_name,
            specialty="General",  # placeholder — can be updated via PATCH later
        )
        db.add(doctor)

    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise _NOT_FOUND_OR_BAD_PASSWORD

    token_data = {"sub": str(user.id), "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    _set_auth_cookies(response, access_token, refresh_token)

    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        user_id: str = payload["sub"]
        role: str = payload["role"]
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    token_data = {"sub": str(user.id), "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token_new = create_refresh_token(token_data)

    _set_auth_cookies(response, access_token, refresh_token_new)

    return TokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    _clear_auth_cookies(response)
