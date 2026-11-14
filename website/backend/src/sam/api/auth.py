from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sam.db import get_db
from sam.models.user import User
from sam.schemas.auth import (
    SetupStatusResponse,
    InitAdminRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
)
from sam.services.auth_service import hash_password, verify_password, create_access_token
from sam.api.deps import get_current_user

router = APIRouter(tags=["Setup & Auth"])


@router.get("/setup/status", response_model=SetupStatusResponse)
async def get_setup_status(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count(User.id)))
    count = result.scalar_one()
    return {"is_initialized": count > 0}


@router.post("/setup/init-admin")
async def init_admin(payload: InitAdminRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count(User.id)))
    count = result.scalar_one()
    if count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Система уже инициализирована. Используйте вход через /auth/login.",
        )

    admin_user = User(
        username=payload.username.strip(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name or "Администратор SAM",
        role="admin",
    )
    db.add(admin_user)
    await db.commit()
    await db.refresh(admin_user)

    token = create_access_token({"sub": admin_user.username, "role": admin_user.role})
    return {"success": True, "token": token}


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == payload.username.strip()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
        )

    token = create_access_token({"sub": user.username, "role": user.role})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "username": current_user.username,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "created_at": current_user.created_at,
    }
