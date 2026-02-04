"""add feedback and golden examples tables

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-02-03

This migration adds:
1. message_feedback - Stores user feedback (thumbs up/down) on AI responses
2. golden_examples - Stores admin-curated ideal responses for RAG-based learning
3. Adds feedback settings to the settings table

The human feedback loop allows:
- Users to rate AI responses (positive/negative) with optional reason
- Admins to review feedback and create golden examples
- Auto-approval of feedback based on configurable settings
- AI to use golden examples as few-shot examples via semantic search
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'h8i9j0k1l2m3'
down_revision: Union[str, Sequence[str], None] = 'g7h8i9j0k1l2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add feedback and golden examples tables."""
    op.create_table(
        'message_feedback',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('message_id', UUID(as_uuid=True), sa.ForeignKey('messages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('feedback_type', sa.String(20), nullable=False, comment='positive or negative'),
        sa.Column('reason', sa.Text, nullable=True, comment='Optional user explanation'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending', 
                  comment='pending, auto_approved, reviewed, dismissed'),
        sa.Column('reviewed_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False)
    )

    op.create_table(
        'golden_examples',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('feedback_id', UUID(as_uuid=True), sa.ForeignKey('message_feedback.id', ondelete='SET NULL'), nullable=True),
        sa.Column('source_type', sa.String(20), nullable=False, comment='positive, negative, or manual'),
        sa.Column('approval_type', sa.String(20), nullable=False, server_default='manual', comment='auto or manual'),
        sa.Column('original_query', sa.Text, nullable=False),
        sa.Column('original_response', sa.Text, nullable=False),
        sa.Column('golden_response', sa.Text, nullable=False),
        sa.Column('qdrant_point_id', sa.String(100), nullable=True, comment='Reference to vector in Qdrant'),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True)
    )

    op.add_column('settings', sa.Column('feedback_auto_approve_positive', sa.Boolean, server_default='true', nullable=False))
    op.add_column('settings', sa.Column('feedback_auto_approve_negative', sa.Boolean, server_default='false', nullable=False))
    op.add_column('settings', sa.Column('feedback_require_reason_positive', sa.Boolean, server_default='false', nullable=False))
    op.add_column('settings', sa.Column('feedback_require_reason_negative', sa.Boolean, server_default='false', nullable=False))

    op.create_index('idx_message_feedback_message_id', 'message_feedback', ['message_id'])
    op.create_index('idx_message_feedback_user_id', 'message_feedback', ['user_id'])
    op.create_index('idx_message_feedback_status', 'message_feedback', ['status'])
    op.create_index('idx_message_feedback_type', 'message_feedback', ['feedback_type'])
    op.create_index('idx_message_feedback_created_at', 'message_feedback', ['created_at'])
    op.create_index('idx_message_feedback_status_type', 'message_feedback', ['status', 'feedback_type'])

    op.create_index('idx_golden_examples_feedback_id', 'golden_examples', ['feedback_id'])
    op.create_index('idx_golden_examples_source_type', 'golden_examples', ['source_type'])
    op.create_index('idx_golden_examples_is_active', 'golden_examples', ['is_active'])
    op.create_index('idx_golden_examples_created_at', 'golden_examples', ['created_at'])
    op.create_index('idx_golden_examples_qdrant_point_id', 'golden_examples', ['qdrant_point_id'])

    op.execute("""
        INSERT INTO permissions (id, name, code, description, category, is_system, created_at)
        VALUES 
            (gen_random_uuid(), 'View Feedback', 'feedback.view', 'View user feedback on AI responses', 'feedback', true, now()),
            (gen_random_uuid(), 'Manage Feedback', 'feedback.manage', 'Review and resolve user feedback', 'feedback', true, now()),
            (gen_random_uuid(), 'View Golden Examples', 'golden_example.view', 'View golden examples', 'feedback', true, now()),
            (gen_random_uuid(), 'Create Golden Examples', 'golden_example.create', 'Create golden examples from feedback', 'feedback', true, now()),
            (gen_random_uuid(), 'Edit Golden Examples', 'golden_example.edit', 'Edit existing golden examples', 'feedback', true, now()),
            (gen_random_uuid(), 'Delete Golden Examples', 'golden_example.delete', 'Delete golden examples', 'feedback', true, now())
        ON CONFLICT (code) DO NOTHING;
    """)

    op.execute("""
        INSERT INTO permission_set_permissions (permission_set_id, permission_id)
        SELECT ps.id, p.id
        FROM permission_sets ps
        CROSS JOIN permissions p
        WHERE ps.code = 'full_admin'
        AND p.code IN (
            'feedback.view', 'feedback.manage',
            'golden_example.view', 'golden_example.create',
            'golden_example.edit', 'golden_example.delete'
        )
        ON CONFLICT DO NOTHING;
    """)


def downgrade() -> None:
    """Remove feedback and golden examples tables."""

    op.drop_index('idx_golden_examples_qdrant_point_id', table_name='golden_examples')
    op.drop_index('idx_golden_examples_created_at', table_name='golden_examples')
    op.drop_index('idx_golden_examples_is_active', table_name='golden_examples')
    op.drop_index('idx_golden_examples_source_type', table_name='golden_examples')
    op.drop_index('idx_golden_examples_feedback_id', table_name='golden_examples')

    op.drop_index('idx_message_feedback_status_type', table_name='message_feedback')
    op.drop_index('idx_message_feedback_created_at', table_name='message_feedback')
    op.drop_index('idx_message_feedback_type', table_name='message_feedback')
    op.drop_index('idx_message_feedback_status', table_name='message_feedback')
    op.drop_index('idx_message_feedback_user_id', table_name='message_feedback')
    op.drop_index('idx_message_feedback_message_id', table_name='message_feedback')

    op.drop_column('settings', 'feedback_require_reason_negative')
    op.drop_column('settings', 'feedback_require_reason_positive')
    op.drop_column('settings', 'feedback_auto_approve_negative')
    op.drop_column('settings', 'feedback_auto_approve_positive')

    op.drop_table('golden_examples')
    op.drop_table('message_feedback')

    op.execute("""
        DELETE FROM permissions 
        WHERE code IN (
            'feedback.view', 'feedback.manage', 
            'golden_example.view', 'golden_example.create', 
            'golden_example.edit', 'golden_example.delete'
        );
    """)
