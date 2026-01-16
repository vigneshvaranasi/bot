import asyncio
import sys
import os
from uuid import uuid4

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from passlib.context import CryptContext

from src.api.db.session import async_session
from src.api.db.models.user import User
from src.api.db.models.role import Role
from src.api.db.models.auth_identity import AuthIdentity

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_admin_user():
    async with async_session() as session:
        # Check if admin role exists
        result = await session.execute(select(Role).where(Role.name == "admin"))
        admin_role = result.scalar_one_or_none()
        
        if not admin_role:
            print("Admin role not found. Please run migrations first.")
            return

        email = "admin@gmail.com"
        password = "admin"
        
        # Check if user exists
        result = await session.execute(select(User).where(User.email == email))
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            print(f"User {email} already exists.")
            user_id = existing_user.id
        else:
            print(f"Creating user {email}...")
            user_id = uuid4()
            new_user = User(
                id=user_id,
                email=email,
                role_id=admin_role.id,
                is_active=True,
                token_version=0
            )
            session.add(new_user)
            await session.commit()
            print(f"User {email} created.")

        # Check if auth identity exists
        result = await session.execute(
            select(AuthIdentity).where(
                AuthIdentity.provider == "local",
                AuthIdentity.provider_user_id == email
            )
        )
        existing_identity = result.scalar_one_or_none()
        
        if existing_identity:
            print("Auth identity already exists.")
        else:
            print("Creating auth identity...")
            password_hash = pwd_context.hash(password)
            new_identity = AuthIdentity(
                id=uuid4(),
                user_id=user_id,
                provider="local",
                provider_user_id=email,
                password_hash=password_hash
            )
            session.add(new_identity)
            await session.commit()
            print("Auth identity created.")

if __name__ == "__main__":
    asyncio.run(create_admin_user())
