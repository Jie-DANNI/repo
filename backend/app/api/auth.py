"""认证路由：注册 / 登录 / 当前用户。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db import get_db
from app.models.user import User
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterIn, db: AsyncSession = Depends(get_db)):
    """注册即登录：直接返回 token，减少一次跳转（前端体验更好）。"""
    exists = (
        await db.execute(select(User.id).where(User.email == payload.email))
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="该邮箱已注册，请直接登录")

    user = User(
        email=payload.email,
        nickname=payload.nickname.strip(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        # 并发注册同一邮箱时的兜底
        await db.rollback()
        raise HTTPException(status_code=409, detail="该邮箱已注册，请直接登录")
    await db.refresh(user)

    return TokenOut(
        access_token=create_access_token(user.id, user.role),
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)):
    user = (
        await db.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    # 不区分"邮箱不存在"和"密码错误"，避免账号枚举
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    return TokenOut(
        access_token=create_access_token(user.id, user.role),
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)
