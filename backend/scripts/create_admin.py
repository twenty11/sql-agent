"""
初始化管理员账号脚本

用法:
    python scripts/create_admin.py
    python scripts/create_admin.py --email admin@company.com --password mypassword

如果不传参数，将使用交互式输入。
"""

import argparse
import asyncio
import sys
import os

# 将项目根目录加入 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def create_admin(email: str, password: str, full_name: str = "系统管理员"):
    from db.async_connection import AsyncSessionLocal
    from db.crud.users import get_user_by_email, create_user
    from db.crud.roles import assign_role_to_user
    from auth.jwt_handler import hash_password

    async with AsyncSessionLocal() as db:
        # 检查是否已存在
        existing = await get_user_by_email(db, email)
        if existing:
            print(f"❌ 用户 {email} 已存在，如需重置密码请使用 --reset-password 选项")
            return False

        # 创建用户
        user = await create_user(
            db,
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
        )

        # 绑定 admin 角色
        ok = await assign_role_to_user(db, user.id, "admin")
        if not ok:
            print("⚠️  admin 角色不存在，请先执行 alembic upgrade head")
            return False

        print(f"✅ 管理员账号创建成功！")
        print(f"   邮箱: {email}")
        print(f"   姓名: {full_name}")
        print(f"   角色: admin")
        print(f"   用户ID: {user.id}")
        return True


async def reset_password(email: str, new_password: str):
    from db.async_connection import AsyncSessionLocal
    from db.crud.users import get_user_by_email, update_user
    from auth.jwt_handler import hash_password

    async with AsyncSessionLocal() as db:
        user = await get_user_by_email(db, email)
        if not user:
            print(f"❌ 用户 {email} 不存在")
            return False

        await update_user(db, user.id, hashed_password=hash_password(new_password))
        print(f"✅ 用户 {email} 密码已重置")
        return True


def prompt_input(prompt: str, secret: bool = False) -> str:
    if secret:
        import getpass
        return getpass.getpass(prompt)
    return input(prompt).strip()


def main():
    parser = argparse.ArgumentParser(description="创建 DataLens 管理员账号")
    parser.add_argument("--email", help="管理员邮箱")
    parser.add_argument("--password", help="管理员密码")
    parser.add_argument("--name", default="系统管理员", help="管理员姓名（默认：系统管理员）")
    parser.add_argument("--reset-password", action="store_true", help="重置已有用户的密码")
    args = parser.parse_args()

    # 交互式补全缺失参数
    email = args.email or prompt_input("邮箱: ")
    if not email:
        print("❌ 邮箱不能为空")
        sys.exit(1)

    password = args.password or prompt_input("密码: ", secret=True)
    if not password or len(password) < 6:
        print("❌ 密码不能为空且长度不少于 6 位")
        sys.exit(1)

    if args.reset_password:
        success = asyncio.run(reset_password(email, password))
    else:
        success = asyncio.run(create_admin(email, password, full_name=args.name))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
