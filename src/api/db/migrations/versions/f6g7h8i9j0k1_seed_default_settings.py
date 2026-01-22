"""seed default settings

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-01-20

This migration seeds default settings for the application.
It uses the first Super Admin user to associate the settings with.
If no users exist, settings will be created when the first admin logs in.
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6g7h8i9j0k1'
down_revision: Union[str, Sequence[str], None] = 'e5f6g7h8i9j0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Default settings values
DEFAULT_SETTINGS = {
    "model": "gpt-oss:20b",
    "temperature": "0.33",
    "deny_words": "",
    "langfuse_enabled": False,
    "auth_google_enabled": True,
    "auth_github_enabled": True,
    "auth_microsoft_enabled": True,
    "auth_local_enabled": True,
    "change_type": "create",
}


def upgrade() -> None:
    """Seed default settings if a Super Admin user exists."""
    conn = op.get_bind()

    # Check if settings already exist
    existing_settings = conn.execute(
        sa.text("SELECT COUNT(*) FROM settings")
    ).scalar()

    if existing_settings > 0:
        print("Settings already exist, skipping seed")
        return

    # Find the first Super Admin user to associate settings with
    # First try to find a Super Admin role
    super_admin_role = conn.execute(
        sa.text("SELECT id FROM roles WHERE name = 'Super Admin' LIMIT 1")
    ).fetchone()

    user_id = None

    if super_admin_role:
        # Find a user with Super Admin role
        user_result = conn.execute(
            sa.text("""
                SELECT u.id FROM users u
                JOIN user_roles ur ON u.id = ur.user_id
                WHERE ur.role_id = :role_id
                LIMIT 1
            """),
            {"role_id": str(super_admin_role[0])}
        ).fetchone()

        if user_result:
            user_id = str(user_result[0])

    # If no Super Admin, try to find any user
    if not user_id:
        any_user = conn.execute(
            sa.text("SELECT id FROM users LIMIT 1")
        ).fetchone()

        if any_user:
            user_id = str(any_user[0])

    if not user_id:
        print("No users found, skipping settings seed. Defaults will be used.")
        return

    # Create the default settings
    settings_id = str(uuid.uuid4())
    conn.execute(
        sa.text("""
            INSERT INTO settings (
                id, user_id, model, temperature, deny_words,
                langfuse_enabled, auth_google_enabled, auth_github_enabled,
                auth_microsoft_enabled, auth_local_enabled, change_type
            ) VALUES (
                :id, :user_id, :model, :temperature, :deny_words,
                :langfuse_enabled, :auth_google_enabled, :auth_github_enabled,
                :auth_microsoft_enabled, :auth_local_enabled, :change_type
            )
        """),
        {
            "id": settings_id,
            "user_id": user_id,
            **DEFAULT_SETTINGS,
        }
    )

    print(f"Created default settings with id {settings_id}")


def downgrade() -> None:
    """Remove seeded default settings."""
    conn = op.get_bind()

    # Only delete if there's exactly one setting with change_type='create' and no other settings
    count = conn.execute(
        sa.text("SELECT COUNT(*) FROM settings")
    ).scalar()

    if count == 1:
        # Delete the single seeded setting
        conn.execute(
            sa.text("DELETE FROM settings WHERE change_type = 'create'")
        )
        print("Removed seeded default settings")
    else:
        print("Multiple settings exist, not removing any")
