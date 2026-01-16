import asyncio
import sys
import os

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from src.api.db.session import async_session
from src.api.db.models.user import User

async def delete_admin_user():
    async with async_session() as session:
        email = "admin@gmail.com"
        
        # Check if user exists
        result = await session.execute(select(User).where(User.email == email))
        existing_user = result.scalar_one_or_none()
        
        if not existing_user:
            print(f"User {email} does not exist.")
            return

        print(f"Deleting user {email}...")
        await session.delete(existing_user)
        await session.commit()
        print(f"User {email} deleted.")

if __name__ == "__main__":
    asyncio.run(delete_admin_user())
