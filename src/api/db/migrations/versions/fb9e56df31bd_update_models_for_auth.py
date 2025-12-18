"""consolidated auth migration

Revision ID: fb9e56df31bd
Revises: 68e99f253c6c
Create Date: 2025-12-15 11:59:04.790462

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid
import json
import os
from dotenv import load_dotenv

load_dotenv()

# revision identifiers, used by Alembic.
revision: str = 'fb9e56df31bd'
down_revision: Union[str, Sequence[str], None] = '68e99f253c6c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Drop old tables
    # Check if tables exist before dropping to be safe, or just drop them.
    # Since this is a migration, we assume the state is at 68e99f253c6c.
    op.drop_table('user_permission')
    op.drop_table('role_permission')
    op.drop_table('permissions')
    op.drop_table('settings')

    # 2. Create new tables
    op.create_table('auth_providers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('provider_name', sa.String(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider_name')
    )
    
    op.create_table('revoked_tokens',
        sa.Column('jti', sa.String(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('jti')
    )
    
    op.create_table('auth_identities',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('provider_user_id', sa.String(), nullable=True),
        sa.Column('password_hash', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'provider_user_id', name='uq_auth_identity_provider_user_id')
    )

    op.create_table('settings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('deny_words', sa.Text(), nullable=True),
        sa.Column('model', sa.String(), nullable=True),
        sa.Column('temperature', sa.String(), nullable=True),
        sa.Column('langfuse_enabled', sa.Boolean(), nullable=True),
        sa.Column('auth_google_enabled', sa.Boolean(), nullable=True),
        sa.Column('auth_github_enabled', sa.Boolean(), nullable=True),
        sa.Column('auth_local_enabled', sa.Boolean(), nullable=True),
        sa.Column('auth_microsoft_enabled', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 3. Modify existing tables
    # Messages
    op.drop_column('messages', 'deleted_at')
    # Note: created_at is kept as is

    # Users
    op.add_column('users', sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False))
    op.add_column('users', sa.Column('token_version', sa.Integer(), server_default='0', nullable=False))
    op.alter_column('users', 'email', existing_type=sa.VARCHAR(), nullable=True)
    op.drop_column('users', 'password')

    # 4. Insert Data
    # Google
    op.execute(
        sa.text(
            """
            INSERT INTO auth_providers (id, provider_name, enabled, config)
            VALUES (:id, :name, :enabled, :config)
            ON CONFLICT (provider_name) DO NOTHING
            """
        ).bindparams(
            id=uuid.uuid4(),
            name='google',
            enabled=True,
            config=json.dumps({
                "client_id": os.getenv("GOOGLE_CLIENT_ID", "placeholder_id"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", "placeholder_secret"),
                "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5173/auth/callback/google")
            })
        )
    )
    
    # GitHub
    op.execute(
        sa.text(
            """
            INSERT INTO auth_providers (id, provider_name, enabled, config)
            VALUES (:id, :name, :enabled, :config)
            ON CONFLICT (provider_name) DO NOTHING
            """
        ).bindparams(
            id=uuid.uuid4(),
            name='github',
            enabled=True,
            config=json.dumps({
                "client_id": os.getenv("GITHUB_CLIENT_ID", "placeholder_id"),
                "client_secret": os.getenv("GITHUB_CLIENT_SECRET", "placeholder_secret"),
                "redirect_uri": os.getenv("GITHUB_REDIRECT_URI", "http://localhost:5173/auth/callback/github")
            })
        )
    )

    # Microsoft
    op.execute(
        sa.text(
            """
            INSERT INTO auth_providers (id, provider_name, enabled, config)
            VALUES (:id, :name, :enabled, :config)
            ON CONFLICT (provider_name) DO NOTHING
            """
        ).bindparams(
            id=uuid.uuid4(),
            name='microsoft',
            enabled=True,
            config=json.dumps({
                "client_id": os.getenv("MICROSOFT_CLIENT_ID", "placeholder_id"),
                "client_secret": os.getenv("MICROSOFT_CLIENT_SECRET", "placeholder_secret"),
                "redirect_uri": os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:5173/auth/callback/microsoft"),
                "tenant": os.getenv("MICROSOFT_TENANT_ID", "common")
            })
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Revert Users
    op.add_column('users', sa.Column('password', sa.VARCHAR(), autoincrement=False, nullable=False))
    op.alter_column('users', 'email', existing_type=sa.VARCHAR(), nullable=False)
    op.drop_column('users', 'token_version')
    op.drop_column('users', 'is_active')

    # 2. Revert Messages
    op.add_column('messages', sa.Column('deleted_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True))

    # 3. Drop new tables
    op.drop_table('settings')
    op.drop_table('auth_identities')
    op.drop_table('revoked_tokens')
    op.drop_table('auth_providers')

    # 4. Recreate old tables
    op.create_table('permissions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    op.create_table('role_permission',
        sa.Column('role_id', sa.UUID(), nullable=False),
        sa.Column('permission_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='NO ACTION'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='NO ACTION'),
        sa.PrimaryKeyConstraint('role_id', 'permission_id')
    )

    op.create_table('user_permission',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('permission_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='NO ACTION'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='NO ACTION'),
        sa.PrimaryKeyConstraint('user_id', 'permission_id')
    )

    op.create_table('settings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('deny_words', sa.String(), nullable=True),
        sa.Column('model', sa.String(), nullable=True),
        sa.Column('temperature', sa.String(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('langfuse_enabled', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
