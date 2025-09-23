import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("DATABASE_URL not found in environment variables.")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

def add_is_archived_column():
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'chats' AND column_name = 'is_archived'
        """))
        if result.fetchone():
            print("Column 'is_archived' already exists.")
            return

        conn.execute(text("""
            ALTER TABLE chats ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT FALSE
        """))
        conn.commit()
        print("Added 'is_archived' column to 'chats' table.")

if __name__ == "__main__":
    add_is_archived_column()