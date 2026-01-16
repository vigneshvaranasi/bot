import asyncio
import sys
import os
from sqlalchemy import text

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.db.session import engine
from src.api.db.models import *

async def reset_database():
    print("Resetting database...")
    async with engine.begin() as conn:
        # Disable foreign key checks to allow dropping tables in any order
        await conn.execute(text("DROP SCHEMA public CASCADE;"))
        await conn.execute(text("CREATE SCHEMA public;"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
        print("Schema public dropped and recreated.")

    print("Database reset complete.")

if __name__ == "__main__":
    asyncio.run(reset_database())
