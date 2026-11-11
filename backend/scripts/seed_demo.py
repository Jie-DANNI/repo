"""创建评审演示账号（幂等，可重复执行）。

用法: ./.venv/Scripts/python.exe -m scripts.seed_demo
默认账号: demo@memoloop.cn / Demo@2026
"""
import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db import AsyncSessionLocal
from app.models.user import User

DEMO_EMAIL = "demo@memoloop.cn"
DEMO_PASSWORD = "Demo@2026"
DEMO_NICKNAME = "评审演示账号"


async def main() -> None:
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == DEMO_EMAIL))).scalar_one_or_none()
        if user:
            # 修正角色，保证演示接口可用
            user.role = "demo"
            await db.commit()
            print(f"演示账号已存在，已确保 role=demo -> {DEMO_EMAIL}")
            return

        user = User(
            email=DEMO_EMAIL,
            nickname=DEMO_NICKNAME,
            password_hash=hash_password(DEMO_PASSWORD),
            role="demo",
        )
        db.add(user)
        await db.commit()
        print(f"演示账号创建成功: {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
