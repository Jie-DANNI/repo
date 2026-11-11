"""公共依赖：当前登录用户解析、角色校验。"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "登录状态无效或已过期，请重新登录") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if cred is None or not cred.credentials:
        raise _unauthorized("缺少访问令牌")
    payload = decode_token(cred.credentials)
    if not payload:
        raise _unauthorized()
    try:
        user_id = int(payload.get("sub", 0))
    except (TypeError, ValueError):
        raise _unauthorized()
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise _unauthorized("用户不存在")
    return user


async def get_demo_user(user: User = Depends(get_current_user)) -> User:
    """仅评审演示账号可用的接口（如手动推进复习轮次），普通用户 403。"""
    if user.role != "demo":
        raise HTTPException(status_code=403, detail="该功能仅演示账号可用")
    return user
