"""Tests for RBAC audit service.

Validates audit log creation, filtering, entity history retrieval,
and user RBAC change tracking.
"""

import uuid
import pytest
import pytest_asyncio
from sqlalchemy.future import select

from src.api.db.models import RbacAuditLog
from src.api.services.audit_service import (
    log_rbac_change,
    get_audit_logs,
    get_entity_history,
    get_user_rbac_history,
    AuditEntityType,
    AuditAction,
)


class TestLogRbacChange:
    """Tests for log_rbac_change function."""

    @pytest.mark.asyncio
    async def test_creates_audit_log_entry(self, test_session):
        """Creates an audit log entry with all fields."""
        entity_id = uuid.uuid4()
        changed_by = uuid.uuid4()
        log = await log_rbac_change(
            session=test_session,
            entity_type=AuditEntityType.ROLE,
            entity_id=entity_id,
            action=AuditAction.CREATE,
            changed_by=changed_by,
            new_value={"name": "Test Role"},
        )
        assert log is not None
        assert log.entity_type == "role"
        assert log.action == "create"
        assert log.entity_id == entity_id
        assert log.changed_by == changed_by
        assert log.new_value == {"name": "Test Role"}

    @pytest.mark.asyncio
    async def test_stores_old_and_new_values(self, test_session):
        """Stores both old and new values for updates."""
        entity_id = uuid.uuid4()
        log = await log_rbac_change(
            session=test_session,
            entity_type=AuditEntityType.ROLE,
            entity_id=entity_id,
            action=AuditAction.UPDATE,
            old_value={"name": "Old Name"},
            new_value={"name": "New Name"},
        )
        assert log.old_value == {"name": "Old Name"}
        assert log.new_value == {"name": "New Name"}

    @pytest.mark.asyncio
    async def test_stores_secondary_entity_id(self, test_session):
        """Stores secondary entity ID for junction table operations."""
        user_id = uuid.uuid4()
        role_id = uuid.uuid4()
        log = await log_rbac_change(
            session=test_session,
            entity_type=AuditEntityType.USER_ROLE,
            entity_id=user_id,
            secondary_entity_id=role_id,
            action=AuditAction.ASSIGN,
            new_value={"role_id": str(role_id)},
        )
        assert log.secondary_entity_id == role_id

    @pytest.mark.asyncio
    async def test_optional_fields_can_be_null(self, test_session):
        """Optional fields (old_value, changed_by, etc.) can be None."""
        log = await log_rbac_change(
            session=test_session,
            entity_type=AuditEntityType.PERMISSION_SET,
            entity_id=uuid.uuid4(),
            action=AuditAction.DELETE,
        )
        assert log.changed_by is None
        assert log.old_value is None
        assert log.new_value is None
        assert log.ip_address is None
        assert log.user_agent is None

    @pytest.mark.asyncio
    async def test_stores_ip_and_user_agent(self, test_session):
        """Stores IP address and user agent for audit trail."""
        log = await log_rbac_change(
            session=test_session,
            entity_type=AuditEntityType.USER_PERMISSION,
            entity_id=uuid.uuid4(),
            action=AuditAction.ASSIGN,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )
        assert log.ip_address == "192.168.1.1"
        assert log.user_agent == "Mozilla/5.0"


class TestGetAuditLogs:
    """Tests for get_audit_logs query function."""

    @pytest_asyncio.fixture
    async def sample_logs(self, test_session):
        """Create sample audit logs for testing."""
        user_id = uuid.uuid4()
        admin_id = uuid.uuid4()
        logs = []
        for i, (entity_type, action) in enumerate([
            (AuditEntityType.ROLE, AuditAction.CREATE),
            (AuditEntityType.ROLE, AuditAction.UPDATE),
            (AuditEntityType.PERMISSION_SET, AuditAction.CREATE),
            (AuditEntityType.USER_ROLE, AuditAction.ASSIGN),
            (AuditEntityType.USER_PERMISSION, AuditAction.ASSIGN),
        ]):
            log = await log_rbac_change(
                session=test_session,
                entity_type=entity_type,
                entity_id=user_id if entity_type.startswith("user") else uuid.uuid4(),
                action=action,
                changed_by=admin_id,
            )
            logs.append(log)
        return logs, user_id, admin_id

    @pytest.mark.asyncio
    async def test_returns_all_logs_without_filter(self, test_session, sample_logs):
        """Returns all logs when no filters are applied."""
        logs, _, _ = sample_logs
        result, total = await get_audit_logs(test_session)
        assert total == 5
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_filter_by_entity_type(self, test_session, sample_logs):
        """Filters by entity_type."""
        result, total = await get_audit_logs(
            test_session, entity_type=AuditEntityType.ROLE
        )
        assert total == 2
        assert all(log.entity_type == "role" for log in result)

    @pytest.mark.asyncio
    async def test_filter_by_action(self, test_session, sample_logs):
        """Filters by action."""
        result, total = await get_audit_logs(
            test_session, action=AuditAction.CREATE
        )
        assert total == 2
        assert all(log.action == "create" for log in result)

    @pytest.mark.asyncio
    async def test_filter_by_changed_by(self, test_session, sample_logs):
        """Filters by the user who made the change."""
        _, _, admin_id = sample_logs
        result, total = await get_audit_logs(
            test_session, changed_by=admin_id
        )
        assert total == 5

    @pytest.mark.asyncio
    async def test_pagination_limit_offset(self, test_session, sample_logs):
        """Pagination with limit and offset works."""
        result, total = await get_audit_logs(test_session, limit=2, offset=0)
        assert total == 5
        assert len(result) == 2

        result2, _ = await get_audit_logs(test_session, limit=2, offset=2)
        assert len(result2) == 2
        # No overlap
        ids_1 = {r.id for r in result}
        ids_2 = {r.id for r in result2}
        assert ids_1.isdisjoint(ids_2)

    @pytest.mark.asyncio
    async def test_empty_result(self, test_session):
        """Returns empty list and zero count when no logs match."""
        result, total = await get_audit_logs(
            test_session, entity_type="nonexistent_type"
        )
        assert total == 0
        assert len(result) == 0


class TestGetEntityHistory:
    """Tests for get_entity_history."""

    @pytest.mark.asyncio
    async def test_returns_history_for_entity(self, test_session):
        """Returns all logs for a specific entity."""
        entity_id = uuid.uuid4()
        for action in [AuditAction.CREATE, AuditAction.UPDATE, AuditAction.DELETE]:
            await log_rbac_change(
                session=test_session,
                entity_type=AuditEntityType.ROLE,
                entity_id=entity_id,
                action=action,
            )

        history = await get_entity_history(
            test_session, AuditEntityType.ROLE, entity_id
        )
        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_filters_by_secondary_entity(self, test_session):
        """Filters by secondary entity ID."""
        user_id = uuid.uuid4()
        role1_id = uuid.uuid4()
        role2_id = uuid.uuid4()

        await log_rbac_change(
            session=test_session,
            entity_type=AuditEntityType.USER_ROLE,
            entity_id=user_id,
            secondary_entity_id=role1_id,
            action=AuditAction.ASSIGN,
        )
        await log_rbac_change(
            session=test_session,
            entity_type=AuditEntityType.USER_ROLE,
            entity_id=user_id,
            secondary_entity_id=role2_id,
            action=AuditAction.ASSIGN,
        )

        history = await get_entity_history(
            test_session, AuditEntityType.USER_ROLE, user_id,
            secondary_entity_id=role1_id
        )
        assert len(history) == 1


class TestGetUserRbacHistory:
    """Tests for get_user_rbac_history."""

    @pytest.mark.asyncio
    async def test_returns_user_rbac_changes(self, test_session):
        """Returns all RBAC changes related to a user."""
        user_id = uuid.uuid4()

        # User role changes
        await log_rbac_change(
            session=test_session,
            entity_type=AuditEntityType.USER_ROLE,
            entity_id=user_id,
            action=AuditAction.ASSIGN,
        )
        await log_rbac_change(
            session=test_session,
            entity_type=AuditEntityType.USER_PERMISSION,
            entity_id=user_id,
            action=AuditAction.ASSIGN,
        )
        await log_rbac_change(
            session=test_session,
            entity_type=AuditEntityType.USER_PERMISSION_SET,
            entity_id=user_id,
            action=AuditAction.ASSIGN,
        )
        await log_rbac_change(
            session=test_session,
            entity_type=AuditEntityType.ROLE,
            entity_id=user_id,
            action=AuditAction.CREATE,
        )

        history = await get_user_rbac_history(test_session, user_id)
        assert len(history) == 3
        assert all(
            log.entity_type in [
                AuditEntityType.USER_ROLE,
                AuditEntityType.USER_PERMISSION,
                AuditEntityType.USER_PERMISSION_SET,
            ]
            for log in history
        )

    @pytest.mark.asyncio
    async def test_pagination(self, test_session):
        """Pagination works for user RBAC history."""
        user_id = uuid.uuid4()
        for _ in range(5):
            await log_rbac_change(
                session=test_session,
                entity_type=AuditEntityType.USER_ROLE,
                entity_id=user_id,
                action=AuditAction.ASSIGN,
            )

        page1 = await get_user_rbac_history(test_session, user_id, limit=2, offset=0)
        assert len(page1) == 2

        page2 = await get_user_rbac_history(test_session, user_id, limit=2, offset=2)
        assert len(page2) == 2