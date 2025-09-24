import os
import uuid
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit(
        "Set DATABASE_URL environment variable"
    )

engine = create_engine(DATABASE_URL)


def main():
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS personas (
                    id uuid PRIMARY KEY,
                    type varchar(50) NOT NULL UNIQUE
                );
                """
            )
        )

        technical_id = None
        for p_type in ("simple", "straight", "technical"):
            new_id = str(uuid.uuid4())
            res = conn.execute(
                text(
                    """
                    INSERT INTO personas (id, type)
                    VALUES (:id, :type)
                    ON CONFLICT (type) DO UPDATE SET type = EXCLUDED.type
                    RETURNING id;
                    """
                ),
                {"id": new_id, "type": p_type},
            )
            row = res.fetchone()
            if p_type == "technical":
                technical_id = row[0]

        if technical_id is None:
            raise SystemExit("failed to create/lookup 'technical' persona")

        conn.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS persona_id uuid;
                """
            )
        )

        conn.execute(
            text(
                """
                UPDATE users
                SET persona_id = :technical_id
                WHERE persona_id IS NULL;
                """
            ),
            {"technical_id": str(technical_id)},
        )

        try:
            conn.execute(
                text(
                    """
                    ALTER TABLE users
                    ADD CONSTRAINT fk_users_persona_id_personas
                    FOREIGN KEY (persona_id) REFERENCES personas (id) ON DELETE SET NULL;
                    """
                )
            )
        except Exception:
            pass

        conn.execute(
            text(
                """
                ALTER TABLE users
                ALTER COLUMN persona_id SET DEFAULT :technical_id;
                """
            ),
            {"technical_id": str(technical_id)},
        )

    print("Done")


if __name__ == "__main__":
    main()
