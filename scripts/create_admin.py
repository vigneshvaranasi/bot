"""
Create Admin Script

Creates a Super Admin user with full permissions for initial system setup.
This admin will have all permissions and can manage other users, roles, and settings.

Usage:
    python scripts/create_admin.py [email] [password]

    If email/password not provided, defaults to admin@gmail.com / admin
"""

import asyncio
import sys
import os
from uuid import uuid4
from datetime import datetime

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from passlib.context import CryptContext

from src.api.db.session import async_session
from src.api.db.models.user import User
from src.api.db.models.role import Role
from src.api.db.models.auth_identity import AuthIdentity
from src.api.db.models.user_role import UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_admin_user(email: str = "admin@gmail.com", password: str = "admin"):
    """Create a Super Admin user with full RBAC permissions.

    Args:
        email: Admin email address
        password: Admin password (will be hashed)
    """
    async with async_session() as session:
        # Check if Super Admin role exists
        result = await session.execute(
            select(Role).where(Role.name == "Super Admin")
        )
        admin_role = result.scalar_one_or_none()

        if not admin_role:
            # Try legacy 'admin' role name
            result = await session.execute(
                select(Role).where(Role.name == "admin")
            )
            admin_role = result.scalar_one_or_none()

        if not admin_role:
            print("❌ Super Admin role not found. Please run migrations first:")
            print("   cd src/api/db && alembic upgrade head")
            return False

        print(f"✓ Found role: {admin_role.name} (ID: {admin_role.id})")

        # Check if user exists
        result = await session.execute(
            select(User).where(User.email == email)
        )
        existing_user = result.scalar_one_or_none()

        user_id = None
        if existing_user:
            print(f"✓ User {email} already exists (ID: {existing_user.id})")
            user_id = existing_user.id

            # Update legacy role_id if not set
            if existing_user.role_id != admin_role.id:
                existing_user.role_id = admin_role.id
                print(f"  → Updated legacy role_id to Super Admin")
        else:
            print(f"→ Creating user {email}...")
            user_id = uuid4()
            new_user = User(
                id=user_id,
                email=email,
                role_id=admin_role.id,  # Legacy field for backward compatibility
                is_active=True,
                token_version=0
            )
            session.add(new_user)
            await session.flush()  # Get the user ID before commit
            print(f"✓ User created (ID: {user_id})")

        # Check if user_roles entry exists (new RBAC system)
        result = await session.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == admin_role.id
            )
        )
        existing_user_role = result.scalar_one_or_none()

        if existing_user_role:
            print(f"✓ User already has Super Admin role in user_roles table")
        else:
            print(f"→ Adding Super Admin role to user_roles table...")
            new_user_role = UserRole(
                user_id=user_id,
                role_id=admin_role.id,
                assigned_at=datetime.utcnow(),
                assigned_by=None  # Self-assigned during setup
            )
            session.add(new_user_role)
            print(f"✓ Role assignment created")

        # Check if auth identity exists
        result = await session.execute(
            select(AuthIdentity).where(
                AuthIdentity.provider == "local",
                AuthIdentity.provider_user_id == email
            )
        )
        existing_identity = result.scalar_one_or_none()

        if existing_identity:
            print(f"✓ Auth identity already exists for local provider")
            # Optionally update password
            if password != "admin":  # Only update if non-default password provided
                existing_identity.password_hash = pwd_context.hash(password)
                print(f"  → Updated password")
        else:
            print(f"→ Creating auth identity...")
            password_hash = pwd_context.hash(password)
            new_identity = AuthIdentity(
                id=uuid4(),
                user_id=user_id,
                provider="local",
                provider_user_id=email,
                password_hash=password_hash
            )
            session.add(new_identity)
            print(f"✓ Auth identity created")

        await session.commit()

        print("\n" + "="*50)
        print("✓ Admin user setup complete!")
        print("="*50)
        print(f"\n  Email:    {email}")
        print(f"  Password: {'*' * len(password)}")
        print(f"  Role:     Super Admin (full permissions)")
        print(f"\nThis admin can:")
        print("  • Manage all AI/ML settings")
        print("  • Configure authentication providers")
        print("  • Manage LLM providers and integrations")
        print("  • Create, edit, and delete users")
        print("  • Manage roles and permission sets")
        print("  • View configuration history and rollback")
        print("  • Access all system features")
        print()

        return True


if __name__ == "__main__":
    # Parse command line arguments
    email = sys.argv[1] if len(sys.argv) > 1 else "admin@gmail.com"
    password = sys.argv[2] if len(sys.argv) > 2 else "admin"

    print("\n" + "="*50)
    print("Creating Super Admin User")
    print("="*50 + "\n")

    success = asyncio.run(create_admin_user(email, password))
    sys.exit(0 if success else 1)
