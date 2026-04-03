"""Comprehensive tests for Feedback & Golden Example endpoints (/feedback).

Covers:
- Submit feedback (POST /)
- Get user feedback for message (GET /message/{message_id})
- Admin list feedback (GET /admin/list)
- Admin stats (GET /admin/stats)
- Admin settings get/update (GET/PUT /admin/settings)
- Admin feedback detail (GET /admin/{feedback_id})
- Resolve feedback (POST /admin/{feedback_id}/resolve)
- Dismiss feedback (POST /admin/{feedback_id}/dismiss)
- Restore feedback (POST /admin/{feedback_id}/restore)
- Delete feedback (DELETE /admin/{feedback_id})
- Generate golden response (POST /admin/{feedback_id}/generate-response)
- Golden examples CRUD (GET/POST/PUT/DELETE /golden-examples/)
- Permission enforcement (no_perms_client => 403)
- Unauthenticated access (client => 403)
"""

import pytest
from uuid import uuid4
from unittest.mock import patch, AsyncMock, MagicMock

from sqlalchemy.future import select

from src.api.db.models import Chat, Message, User, Setting, MessageFeedback, GoldenExample


# ============================================================
# Helpers
# ============================================================

def _make_user(user_id, *, email="test@example.com"):
    return User(id=user_id, email=email, is_active=True)


def _make_chat(user_id, *, title="Test Chat"):
    return Chat(user_id=user_id, title=title)


def _make_message(chat_id, *, human="How do I reset my password?", bot="Go to settings and click reset."):
    return Message(chat_id=chat_id, human=human, bot=bot)


def _make_feedback(message_id, user_id, *, feedback_type="positive", reason=None, status="pending"):
    return MessageFeedback(
        message_id=message_id,
        user_id=user_id,
        feedback_type=feedback_type,
        reason=reason,
        status=status,
    )


def _make_golden_example(*, original_query="What is X?", original_response="X is Y",
                         golden_response="X is the best Y", source_type="manual",
                         approval_type="manual", created_by=None, feedback_id=None,
                         is_active=True):
    return GoldenExample(
        original_query=original_query,
        original_response=original_response,
        golden_response=golden_response,
        source_type=source_type,
        approval_type=approval_type,
        created_by=created_by,
        feedback_id=feedback_id,
        is_active=is_active,
    )


def _make_setting(user_id, **overrides):
    defaults = dict(
        user_id=user_id,
        model="claude-3-5-sonnet",
        temperature="0.5",
        deny_words="",
        langfuse_enabled=False,
        allow_user_model_selection=False,
        auth_google_enabled=True,
        auth_github_enabled=True,
        auth_microsoft_enabled=True,
        auth_local_enabled=True,
        change_type="create",
        feedback_auto_approve_positive=True,
        feedback_auto_approve_negative=False,
        feedback_require_reason_positive=False,
        feedback_require_reason_negative=False,
    )
    defaults.update(overrides)
    return Setting(**defaults)


async def _seed(session, user_id, *, email="test@example.com",
                human="Test question", bot="Test answer"):
    """Create User + Chat + Message, return (user, chat, message)."""
    user = _make_user(user_id, email=email)
    session.add(user)
    await session.flush()
    chat = _make_chat(user_id)
    session.add(chat)
    await session.flush()
    msg = _make_message(chat.id, human=human, bot=bot)
    session.add(msg)
    await session.commit()
    return user, chat, msg


async def _seed_extra_message(session, user_id, *, human="Q2", bot="A2"):
    """Create an extra Chat + Message for the same user. Returns (chat, msg)."""
    chat = _make_chat(user_id)
    session.add(chat)
    await session.flush()
    msg = _make_message(chat.id, human=human, bot=bot)
    session.add(msg)
    await session.flush()
    return chat, msg


# ============================================================
# POST /feedback/ — Submit feedback
# ============================================================


class TestSubmitFeedback:
    """Tests for POST /feedback/"""

    @pytest.mark.asyncio
    async def test_submit_positive_auto_approved(self, admin_client):
        """Positive feedback is auto-approved by default settings."""
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)

        with patch(
            "src.api.services.golden_example_service.GoldenExampleService._embed_example",
            new_callable=AsyncMock, return_value="mock-point",
        ):
            response = await client.post("/feedback/", json={
                "message_id": str(msg.id),
                "feedback_type": "positive",
            })
        assert response.status_code == 201
        data = response.json()
        assert data["feedback_type"] == "positive"
        assert data["status"] == "auto_approved"
        assert data["message_id"] == str(msg.id)

    @pytest.mark.asyncio
    async def test_submit_negative_pending(self, admin_client):
        """Negative feedback is pending by default (auto_approve_negative=False)."""
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)

        response = await client.post("/feedback/", json={
            "message_id": str(msg.id),
            "feedback_type": "negative",
            "reason": "Response was wrong",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["feedback_type"] == "negative"
        assert data["status"] == "pending"
        assert data["reason"] == "Response was wrong"

    @pytest.mark.asyncio
    async def test_submit_feedback_with_reason(self, admin_client):
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)

        with patch(
            "src.api.services.golden_example_service.GoldenExampleService._embed_example",
            new_callable=AsyncMock, return_value="p",
        ):
            response = await client.post("/feedback/", json={
                "message_id": str(msg.id),
                "feedback_type": "positive",
                "reason": "Very helpful!",
            })
        assert response.status_code == 201
        assert response.json()["reason"] == "Very helpful!"

    @pytest.mark.asyncio
    async def test_submit_duplicate_rejected(self, admin_client):
        """Cannot submit feedback twice for the same message."""
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        session.add(_make_feedback(msg.id, user_id))
        await session.commit()

        response = await client.post("/feedback/", json={
            "message_id": str(msg.id),
            "feedback_type": "positive",
        })
        assert response.status_code == 400
        assert "already submitted" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_submit_feedback_invalid_message(self, admin_client):
        """Feedback for non-existent message returns 400."""
        client, _, _ = admin_client
        response = await client.post("/feedback/", json={
            "message_id": str(uuid4()),
            "feedback_type": "positive",
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_submit_feedback_invalid_type(self, admin_client):
        """Invalid feedback_type rejected by Pydantic."""
        client, _, _ = admin_client
        response = await client.post("/feedback/", json={
            "message_id": str(uuid4()),
            "feedback_type": "neutral",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_submit_feedback_missing_fields(self, admin_client):
        client, _, _ = admin_client
        response = await client.post("/feedback/", json={"feedback_type": "positive"})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_submit_feedback_response_format(self, admin_client):
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)

        with patch(
            "src.api.services.golden_example_service.GoldenExampleService._embed_example",
            new_callable=AsyncMock, return_value="p",
        ):
            response = await client.post("/feedback/", json={
                "message_id": str(msg.id),
                "feedback_type": "positive",
            })
        data = response.json()
        for field in ("id", "message_id", "user_id", "feedback_type", "status", "created_at"):
            assert field in data

    @pytest.mark.asyncio
    async def test_submit_feedback_unauthenticated(self, client):
        response = await client.post("/feedback/", json={
            "message_id": str(uuid4()),
            "feedback_type": "positive",
        })
        assert response.status_code == 403


# ============================================================
# GET /feedback/message/{message_id} — Get user's feedback
# ============================================================


class TestGetFeedbackForMessage:
    """Tests for GET /feedback/message/{message_id}"""

    @pytest.mark.asyncio
    async def test_get_feedback_exists(self, admin_client):
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        session.add(_make_feedback(msg.id, user_id, feedback_type="negative", reason="Bad"))
        await session.commit()

        response = await client.get(f"/feedback/message/{msg.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["feedback_type"] == "negative"
        assert data["reason"] == "Bad"

    @pytest.mark.asyncio
    async def test_get_feedback_none(self, admin_client):
        """Returns null when no feedback exists."""
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)

        response = await client.get(f"/feedback/message/{msg.id}")
        assert response.status_code == 200
        assert response.json() is None

    @pytest.mark.asyncio
    async def test_get_feedback_nonexistent_message(self, admin_client):
        """Returns null for non-existent message."""
        client, _, _ = admin_client
        response = await client.get(f"/feedback/message/{uuid4()}")
        assert response.status_code == 200
        assert response.json() is None

    @pytest.mark.asyncio
    async def test_get_feedback_unauthenticated(self, client):
        response = await client.get(f"/feedback/message/{uuid4()}")
        assert response.status_code == 403


# ============================================================
# GET /feedback/admin/list — Admin list feedback
# ============================================================


class TestAdminListFeedback:
    """Tests for GET /feedback/admin/list"""

    @pytest.mark.asyncio
    async def test_list_empty(self, admin_client):
        client, _, _ = admin_client
        response = await client.get("/feedback/admin/list")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_returns_feedback_with_context(self, admin_client):
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id, human="My VPN is down", bot="Try restarting")
        session.add(_make_feedback(msg.id, user_id, feedback_type="negative", reason="Unhelpful"))
        await session.commit()

        response = await client.get("/feedback/admin/list")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        item = data["items"][0]
        assert item["feedback_type"] == "negative"
        assert item["reason"] == "Unhelpful"
        assert item["original_query"] == "My VPN is down"
        assert item["original_response"] == "Try restarting"

    @pytest.mark.asyncio
    async def test_list_filter_by_status(self, admin_client):
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        _, msg2 = await _seed_extra_message(session, user_id)
        session.add(_make_feedback(msg.id, user_id, status="pending"))
        session.add(_make_feedback(msg2.id, user_id, status="dismissed"))
        await session.commit()

        response = await client.get("/feedback/admin/list?status=pending")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_filter_by_type(self, admin_client):
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        _, msg2 = await _seed_extra_message(session, user_id)
        session.add(_make_feedback(msg.id, user_id, feedback_type="positive"))
        session.add(_make_feedback(msg2.id, user_id, feedback_type="negative"))
        await session.commit()

        response = await client.get("/feedback/admin/list?type=negative")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["feedback_type"] == "negative"

    @pytest.mark.asyncio
    async def test_list_search(self, admin_client):
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id, human="password reset help", bot="Go to settings")
        _, msg2 = await _seed_extra_message(session, user_id, human="VPN issue", bot="Check config")
        session.add(_make_feedback(msg.id, user_id))
        session.add(_make_feedback(msg2.id, user_id))
        await session.commit()

        response = await client.get("/feedback/admin/list?search=password")
        data = response.json()
        assert data["total"] == 1
        assert "password" in data["items"][0]["original_query"].lower()

    @pytest.mark.asyncio
    async def test_list_pagination(self, admin_client):
        client, session, user_id = admin_client
        user = _make_user(user_id)
        session.add(user)
        await session.flush()

        for i in range(5):
            chat, msg = await _seed_extra_message(session, user_id, human=f"Q{i}", bot=f"A{i}")
            session.add(_make_feedback(msg.id, user_id))
        await session.commit()

        response = await client.get("/feedback/admin/list?limit=2&offset=0")
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["limit"] == 2
        assert data["offset"] == 0

    @pytest.mark.asyncio
    async def test_list_no_permission(self, no_perms_client):
        client, _, _ = no_perms_client
        response = await client.get("/feedback/admin/list")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_unauthenticated(self, client):
        response = await client.get("/feedback/admin/list")
        assert response.status_code == 403


# ============================================================
# GET /feedback/admin/stats — Feedback statistics
# ============================================================


class TestFeedbackStats:
    """Tests for GET /feedback/admin/stats"""

    @pytest.mark.asyncio
    async def test_stats_empty(self, admin_client):
        client, _, _ = admin_client
        response = await client.get("/feedback/admin/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_feedback"] == 0
        assert data["positive_count"] == 0
        assert data["negative_count"] == 0
        assert data["pending_count"] == 0
        assert data["golden_examples_count"] == 0

    @pytest.mark.asyncio
    async def test_stats_with_data(self, admin_client):
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        _, msg2 = await _seed_extra_message(session, user_id)
        _, msg3 = await _seed_extra_message(session, user_id, human="Q3", bot="A3")

        session.add(_make_feedback(msg.id, user_id, feedback_type="positive", status="auto_approved"))
        session.add(_make_feedback(msg2.id, user_id, feedback_type="negative", status="pending"))
        session.add(_make_feedback(msg3.id, user_id, feedback_type="positive", status="reviewed"))
        session.add(_make_golden_example(is_active=True))
        await session.commit()

        response = await client.get("/feedback/admin/stats")
        data = response.json()
        assert data["total_feedback"] == 3
        assert data["positive_count"] == 2
        assert data["negative_count"] == 1
        assert data["pending_count"] == 1
        assert data["auto_approved_count"] == 1
        assert data["reviewed_count"] == 1
        assert data["golden_examples_count"] == 1

    @pytest.mark.asyncio
    async def test_stats_no_permission(self, no_perms_client):
        client, _, _ = no_perms_client
        response = await client.get("/feedback/admin/stats")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_stats_unauthenticated(self, client):
        response = await client.get("/feedback/admin/stats")
        assert response.status_code == 403


# ============================================================
# GET/PUT /feedback/admin/settings — Feedback settings
# ============================================================


class TestFeedbackSettings:
    """Tests for GET/PUT /feedback/admin/settings"""

    @pytest.mark.asyncio
    async def test_get_settings_defaults(self, admin_client):
        """Returns defaults when no settings row exists."""
        client, _, _ = admin_client
        response = await client.get("/feedback/admin/settings")
        assert response.status_code == 200
        data = response.json()
        assert data["auto_approve_positive"] is True
        assert data["auto_approve_negative"] is False
        assert data["require_reason_positive"] is False
        assert data["require_reason_negative"] is False

    @pytest.mark.asyncio
    async def test_get_settings_from_db(self, admin_client):
        client, session, user_id = admin_client
        session.add(_make_setting(user_id, feedback_auto_approve_positive=False,
                                  feedback_require_reason_negative=True))
        await session.commit()

        response = await client.get("/feedback/admin/settings")
        data = response.json()
        assert data["auto_approve_positive"] is False
        assert data["require_reason_negative"] is True

    @pytest.mark.asyncio
    async def test_update_settings(self, admin_client):
        client, session, user_id = admin_client
        session.add(_make_setting(user_id))
        await session.commit()

        response = await client.put("/feedback/admin/settings", json={
            "auto_approve_positive": False,
            "auto_approve_negative": True,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["auto_approve_positive"] is False
        assert data["auto_approve_negative"] is True

    @pytest.mark.asyncio
    async def test_update_settings_partial(self, admin_client):
        """Only provided fields are updated."""
        client, session, user_id = admin_client
        session.add(_make_setting(user_id))
        await session.commit()

        response = await client.put("/feedback/admin/settings", json={
            "require_reason_negative": True,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["require_reason_negative"] is True
        assert data["auto_approve_positive"] is True  # unchanged

    @pytest.mark.asyncio
    async def test_get_settings_no_permission(self, no_perms_client):
        client, _, _ = no_perms_client
        response = await client.get("/feedback/admin/settings")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_settings_no_permission(self, no_perms_client):
        client, _, _ = no_perms_client
        response = await client.put("/feedback/admin/settings", json={
            "auto_approve_positive": False,
        })
        assert response.status_code == 403


# ============================================================
# GET /feedback/admin/{feedback_id} — Feedback detail
# ============================================================


class TestAdminFeedbackDetail:
    """Tests for GET /feedback/admin/{feedback_id}"""

    @pytest.mark.asyncio
    async def test_get_detail(self, admin_client):
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id, human="VPN broken", bot="Try restart")
        fb = _make_feedback(msg.id, user_id, feedback_type="negative", reason="Wrong answer")
        session.add(fb)
        await session.commit()
        await session.refresh(fb)

        response = await client.get(f"/feedback/admin/{fb.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["feedback_type"] == "negative"
        assert data["reason"] == "Wrong answer"
        assert data["original_query"] == "VPN broken"
        assert data["original_response"] == "Try restart"
        assert data["has_golden_example"] is False

    @pytest.mark.asyncio
    async def test_get_detail_with_golden_example(self, admin_client):
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id, status="reviewed")
        session.add(fb)
        await session.flush()
        ge = _make_golden_example(feedback_id=fb.id, created_by=user_id)
        session.add(ge)
        await session.commit()
        await session.refresh(fb)

        response = await client.get(f"/feedback/admin/{fb.id}")
        data = response.json()
        assert data["has_golden_example"] is True
        assert data["golden_example_id"] is not None

    @pytest.mark.asyncio
    async def test_get_detail_not_found(self, admin_client):
        client, _, _ = admin_client
        response = await client.get(f"/feedback/admin/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_detail_no_permission(self, no_perms_client):
        client, _, _ = no_perms_client
        response = await client.get(f"/feedback/admin/{uuid4()}")
        assert response.status_code == 403


# ============================================================
# POST /feedback/admin/{feedback_id}/resolve — Resolve
# ============================================================


class TestResolveFeedback:
    """Tests for POST /feedback/admin/{feedback_id}/resolve"""

    @pytest.mark.asyncio
    async def test_resolve_positive_uses_original(self, admin_client):
        """Resolving positive feedback uses original response as golden."""
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id, feedback_type="positive")
        session.add(fb)
        await session.commit()
        await session.refresh(fb)

        with patch(
            "src.api.services.golden_example_service.GoldenExampleService._embed_example",
            new_callable=AsyncMock, return_value="point-1",
        ):
            response = await client.post(f"/feedback/admin/{fb.id}/resolve", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "reviewed"
        assert "golden_example_id" in data

    @pytest.mark.asyncio
    async def test_resolve_negative_with_golden_response(self, admin_client):
        """Negative feedback resolved with a corrected response."""
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id, feedback_type="negative")
        session.add(fb)
        await session.commit()
        await session.refresh(fb)

        with patch(
            "src.api.services.golden_example_service.GoldenExampleService._embed_example",
            new_callable=AsyncMock, return_value="point-2",
        ):
            response = await client.post(f"/feedback/admin/{fb.id}/resolve", json={
                "golden_response": "Corrected answer here.",
            })
        assert response.status_code == 200
        assert response.json()["status"] == "reviewed"

    @pytest.mark.asyncio
    async def test_resolve_negative_without_golden_fails(self, admin_client):
        """Negative feedback without golden_response returns 400."""
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id, feedback_type="negative")
        session.add(fb)
        await session.commit()
        await session.refresh(fb)

        response = await client.post(f"/feedback/admin/{fb.id}/resolve", json={})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_resolve_already_reviewed(self, admin_client):
        """Cannot resolve already-reviewed feedback."""
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id, status="reviewed")
        session.add(fb)
        await session.commit()
        await session.refresh(fb)

        response = await client.post(f"/feedback/admin/{fb.id}/resolve", json={})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_resolve_already_auto_approved(self, admin_client):
        """Cannot resolve auto-approved feedback."""
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id, status="auto_approved")
        session.add(fb)
        await session.commit()
        await session.refresh(fb)

        response = await client.post(f"/feedback/admin/{fb.id}/resolve", json={})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_resolve_not_found(self, admin_client):
        client, _, _ = admin_client
        response = await client.post(f"/feedback/admin/{uuid4()}/resolve", json={})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_resolve_no_permission(self, no_perms_client):
        client, _, _ = no_perms_client
        response = await client.post(f"/feedback/admin/{uuid4()}/resolve", json={})
        assert response.status_code == 403


# ============================================================
# POST /feedback/admin/{feedback_id}/dismiss — Dismiss
# ============================================================


class TestDismissFeedback:
    """Tests for POST /feedback/admin/{feedback_id}/dismiss"""

    @pytest.mark.asyncio
    async def test_dismiss_with_reason(self, admin_client):
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id, feedback_type="negative")
        session.add(fb)
        await session.commit()
        await session.refresh(fb)

        response = await client.post(f"/feedback/admin/{fb.id}/dismiss", json={
            "reason": "Not actionable",
        })
        assert response.status_code == 200
        assert response.json()["status"] == "dismissed"

    @pytest.mark.asyncio
    async def test_dismiss_without_reason(self, admin_client):
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id)
        session.add(fb)
        await session.commit()
        await session.refresh(fb)

        response = await client.post(f"/feedback/admin/{fb.id}/dismiss", json={})
        assert response.status_code == 200
        assert response.json()["status"] == "dismissed"

    @pytest.mark.asyncio
    async def test_dismiss_already_reviewed(self, admin_client):
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id, status="reviewed")
        session.add(fb)
        await session.commit()
        await session.refresh(fb)

        response = await client.post(f"/feedback/admin/{fb.id}/dismiss", json={})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_dismiss_already_dismissed(self, admin_client):
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id, status="dismissed")
        session.add(fb)
        await session.commit()
        await session.refresh(fb)

        response = await client.post(f"/feedback/admin/{fb.id}/dismiss", json={})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_dismiss_not_found(self, admin_client):
        client, _, _ = admin_client
        response = await client.post(f"/feedback/admin/{uuid4()}/dismiss", json={})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_dismiss_no_permission(self, no_perms_client):
        client, _, _ = no_perms_client
        response = await client.post(f"/feedback/admin/{uuid4()}/dismiss", json={})
        assert response.status_code == 403


# ============================================================
# POST /feedback/admin/{feedback_id}/restore — Restore
# ============================================================


class TestRestoreFeedback:
    """Tests for POST /feedback/admin/{feedback_id}/restore"""

    @pytest.mark.asyncio
    async def test_restore_dismissed(self, admin_client):
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id, status="dismissed")
        session.add(fb)
        await session.commit()
        await session.refresh(fb)

        response = await client.post(f"/feedback/admin/{fb.id}/restore")
        assert response.status_code == 200
        assert response.json()["status"] == "pending"

    @pytest.mark.asyncio
    async def test_restore_non_dismissed_fails(self, admin_client):
        """Only dismissed feedback can be restored."""
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id, status="pending")
        session.add(fb)
        await session.commit()
        await session.refresh(fb)

        response = await client.post(f"/feedback/admin/{fb.id}/restore")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_restore_reviewed_fails(self, admin_client):
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id, status="reviewed")
        session.add(fb)
        await session.commit()
        await session.refresh(fb)

        response = await client.post(f"/feedback/admin/{fb.id}/restore")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_restore_not_found(self, admin_client):
        client, _, _ = admin_client
        response = await client.post(f"/feedback/admin/{uuid4()}/restore")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_restore_no_permission(self, no_perms_client):
        client, _, _ = no_perms_client
        response = await client.post(f"/feedback/admin/{uuid4()}/restore")
        assert response.status_code == 403


# ============================================================
# DELETE /feedback/admin/{feedback_id} — Delete feedback
# ============================================================


class TestDeleteFeedback:
    """Tests for DELETE /feedback/admin/{feedback_id}"""

    @pytest.mark.asyncio
    async def test_delete_feedback(self, admin_client):
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id)
        session.add(fb)
        await session.commit()
        await session.refresh(fb)

        response = await client.delete(f"/feedback/admin/{fb.id}")
        assert response.status_code == 200
        assert response.json()["message"] == "Feedback deleted successfully"

    @pytest.mark.asyncio
    async def test_delete_removes_from_db(self, admin_client):
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id)
        session.add(fb)
        await session.commit()
        await session.refresh(fb)
        fb_id = fb.id

        await client.delete(f"/feedback/admin/{fb_id}")

        session.expire_all()
        result = await session.execute(
            select(MessageFeedback).where(MessageFeedback.id == fb_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_with_golden_example(self, admin_client):
        """Deleting feedback also deletes associated golden example."""
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id, status="reviewed")
        session.add(fb)
        await session.flush()
        ge = _make_golden_example(feedback_id=fb.id, created_by=user_id)
        session.add(ge)
        await session.commit()
        await session.refresh(fb)
        fb_id = fb.id

        with patch(
            "src.api.services.golden_example_service.GoldenExampleService._delete_from_qdrant",
            new_callable=AsyncMock,
        ):
            response = await client.delete(f"/feedback/admin/{fb_id}")
        assert response.status_code == 200

        # Golden example should also be gone
        session.expire_all()
        result = await session.execute(
            select(GoldenExample).where(GoldenExample.feedback_id == fb_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_not_found(self, admin_client):
        client, _, _ = admin_client
        response = await client.delete(f"/feedback/admin/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_no_permission(self, no_perms_client):
        client, _, _ = no_perms_client
        response = await client.delete(f"/feedback/admin/{uuid4()}")
        assert response.status_code == 403


# ============================================================
# POST /feedback/admin/{feedback_id}/generate-response
# ============================================================


class TestGenerateGoldenResponse:
    """Tests for POST /feedback/admin/{feedback_id}/generate-response"""

    @pytest.mark.asyncio
    async def test_generate_success(self, admin_client):
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id, feedback_type="negative", reason="Too vague")
        session.add(fb)
        await session.commit()
        await session.refresh(fb)

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.generated_response = "Improved response text"
        mock_result.tool_calls_made = 2
        mock_result.generation_time_ms = 1500
        mock_result.error = None

        mock_generator = AsyncMock()
        mock_generator.generate = AsyncMock(return_value=mock_result)

        with patch(
            "src.api.routers.feedback.get_golden_response_generator",
            return_value=mock_generator,
        ):
            response = await client.post(f"/feedback/admin/{fb.id}/generate-response")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["generated_response"] == "Improved response text"
        assert data["tool_calls_made"] == 2
        assert data["generation_time_ms"] == 1500

    @pytest.mark.asyncio
    async def test_generate_not_found(self, admin_client):
        client, _, _ = admin_client
        response = await client.post(f"/feedback/admin/{uuid4()}/generate-response")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_generate_llm_failure(self, admin_client):
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id, feedback_type="negative")
        session.add(fb)
        await session.commit()
        await session.refresh(fb)

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.generated_response = ""
        mock_result.tool_calls_made = 0
        mock_result.generation_time_ms = 500
        mock_result.error = "LLM timeout"

        mock_generator = AsyncMock()
        mock_generator.generate = AsyncMock(return_value=mock_result)

        with patch(
            "src.api.routers.feedback.get_golden_response_generator",
            return_value=mock_generator,
        ):
            response = await client.post(f"/feedback/admin/{fb.id}/generate-response")
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_generate_no_permission(self, no_perms_client):
        client, _, _ = no_perms_client
        response = await client.post(f"/feedback/admin/{uuid4()}/generate-response")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_generate_unauthenticated(self, client):
        response = await client.post(f"/feedback/admin/{uuid4()}/generate-response")
        assert response.status_code == 403


# ============================================================
# Golden Examples — CRUD
# ============================================================


class TestListGoldenExamples:
    """Tests for GET /feedback/golden-examples/"""

    @pytest.mark.asyncio
    async def test_list_empty(self, admin_client):
        client, _, _ = admin_client
        response = await client.get("/feedback/golden-examples/")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_returns_examples(self, admin_client):
        client, session, _ = admin_client
        session.add(_make_golden_example(original_query="Q1", golden_response="G1"))
        session.add(_make_golden_example(original_query="Q2", golden_response="G2"))
        await session.commit()

        response = await client.get("/feedback/golden-examples/")
        data = response.json()
        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_list_filter_source_type(self, admin_client):
        client, session, _ = admin_client
        session.add(_make_golden_example(source_type="manual"))
        session.add(_make_golden_example(source_type="positive"))
        await session.commit()

        response = await client.get("/feedback/golden-examples/?source_type=manual")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["source_type"] == "manual"

    @pytest.mark.asyncio
    async def test_list_filter_is_active(self, admin_client):
        client, session, _ = admin_client
        session.add(_make_golden_example(is_active=True))
        session.add(_make_golden_example(is_active=False))
        await session.commit()

        response = await client.get("/feedback/golden-examples/?is_active=true")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["is_active"] is True

    @pytest.mark.asyncio
    async def test_list_search(self, admin_client):
        client, session, _ = admin_client
        session.add(_make_golden_example(original_query="How to reset password"))
        session.add(_make_golden_example(original_query="VPN connection issue"))
        await session.commit()

        response = await client.get("/feedback/golden-examples/?search=password")
        data = response.json()
        assert data["total"] == 1
        assert "password" in data["items"][0]["original_query"].lower()

    @pytest.mark.asyncio
    async def test_list_pagination(self, admin_client):
        client, session, _ = admin_client
        for i in range(5):
            session.add(_make_golden_example(original_query=f"Q{i}", golden_response=f"G{i}"))
        await session.commit()

        response = await client.get("/feedback/golden-examples/?limit=2&offset=0")
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5

    @pytest.mark.asyncio
    async def test_list_no_permission(self, no_perms_client):
        client, _, _ = no_perms_client
        response = await client.get("/feedback/golden-examples/")
        assert response.status_code == 403


class TestGetGoldenExample:
    """Tests for GET /feedback/golden-examples/{example_id}"""

    @pytest.mark.asyncio
    async def test_get_example(self, admin_client):
        client, session, _ = admin_client
        ge = _make_golden_example(original_query="Test Q", golden_response="Test G")
        session.add(ge)
        await session.commit()
        await session.refresh(ge)

        response = await client.get(f"/feedback/golden-examples/{ge.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["original_query"] == "Test Q"
        assert data["golden_response"] == "Test G"

    @pytest.mark.asyncio
    async def test_get_example_with_creator(self, admin_client):
        """Response includes creator_email when created_by is set."""
        client, session, user_id = admin_client
        session.add(_make_user(user_id, email="creator@example.com"))
        await session.flush()
        ge = _make_golden_example(created_by=user_id)
        session.add(ge)
        await session.commit()
        await session.refresh(ge)

        response = await client.get(f"/feedback/golden-examples/{ge.id}")
        data = response.json()
        assert data["created_by"] == str(user_id)
        assert data["creator_email"] == "creator@example.com"

    @pytest.mark.asyncio
    async def test_get_example_response_format(self, admin_client):
        client, session, _ = admin_client
        ge = _make_golden_example()
        session.add(ge)
        await session.commit()
        await session.refresh(ge)

        response = await client.get(f"/feedback/golden-examples/{ge.id}")
        data = response.json()
        for field in ("id", "source_type", "approval_type", "original_query",
                      "original_response", "golden_response", "is_active", "created_at"):
            assert field in data

    @pytest.mark.asyncio
    async def test_get_example_not_found(self, admin_client):
        client, _, _ = admin_client
        response = await client.get(f"/feedback/golden-examples/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_example_no_permission(self, no_perms_client):
        client, _, _ = no_perms_client
        response = await client.get(f"/feedback/golden-examples/{uuid4()}")
        assert response.status_code == 403


class TestCreateGoldenExample:
    """Tests for POST /feedback/golden-examples/"""

    @pytest.mark.asyncio
    async def test_create_example(self, admin_client):
        client, session, user_id = admin_client
        session.add(_make_user(user_id))
        await session.commit()

        with patch(
            "src.api.services.golden_example_service.GoldenExampleService._embed_example",
            new_callable=AsyncMock, return_value="mock-point",
        ):
            response = await client.post("/feedback/golden-examples/", json={
                "original_query": "How to fix VPN?",
                "golden_response": "Check your VPN config and restart.",
                "original_response": "Try restarting.",
            })
        assert response.status_code == 201
        data = response.json()
        assert data["original_query"] == "How to fix VPN?"
        assert data["source_type"] == "manual"
        assert data["approval_type"] == "manual"
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_create_without_original_response(self, admin_client):
        client, session, user_id = admin_client
        session.add(_make_user(user_id))
        await session.commit()

        with patch(
            "src.api.services.golden_example_service.GoldenExampleService._embed_example",
            new_callable=AsyncMock, return_value="p",
        ):
            response = await client.post("/feedback/golden-examples/", json={
                "original_query": "Question",
                "golden_response": "Answer",
            })
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_create_missing_required_fields(self, admin_client):
        client, _, _ = admin_client
        response = await client.post("/feedback/golden-examples/", json={
            "original_query": "Q",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_no_permission(self, no_perms_client):
        client, _, _ = no_perms_client
        response = await client.post("/feedback/golden-examples/", json={
            "original_query": "Q", "golden_response": "A",
        })
        assert response.status_code == 403


class TestUpdateGoldenExample:
    """Tests for PUT /feedback/golden-examples/{example_id}"""

    @pytest.mark.asyncio
    async def test_update_golden_response(self, admin_client):
        client, session, _ = admin_client
        ge = _make_golden_example(golden_response="Old answer")
        session.add(ge)
        await session.commit()
        await session.refresh(ge)

        with patch(
            "src.api.services.golden_example_service.GoldenExampleService._embed_example",
            new_callable=AsyncMock, return_value="new-point",
        ), patch(
            "src.api.services.golden_example_service.GoldenExampleService._delete_from_qdrant",
            new_callable=AsyncMock,
        ):
            response = await client.put(f"/feedback/golden-examples/{ge.id}", json={
                "golden_response": "Updated answer",
            })
        assert response.status_code == 200
        assert response.json()["golden_response"] == "Updated answer"

    @pytest.mark.asyncio
    async def test_update_is_active(self, admin_client):
        client, session, _ = admin_client
        ge = _make_golden_example(is_active=True)
        session.add(ge)
        await session.commit()
        await session.refresh(ge)

        response = await client.put(f"/feedback/golden-examples/{ge.id}", json={
            "is_active": False,
        })
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    @pytest.mark.asyncio
    async def test_update_not_found(self, admin_client):
        client, _, _ = admin_client
        response = await client.put(f"/feedback/golden-examples/{uuid4()}", json={
            "golden_response": "X",
        })
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_no_permission(self, no_perms_client):
        client, _, _ = no_perms_client
        response = await client.put(f"/feedback/golden-examples/{uuid4()}", json={
            "golden_response": "X",
        })
        assert response.status_code == 403


class TestDeleteGoldenExample:
    """Tests for DELETE /feedback/golden-examples/{example_id}"""

    @pytest.mark.asyncio
    async def test_delete_example(self, admin_client):
        client, session, _ = admin_client
        ge = _make_golden_example()
        session.add(ge)
        await session.commit()
        await session.refresh(ge)

        with patch(
            "src.api.services.golden_example_service.GoldenExampleService._delete_from_qdrant",
            new_callable=AsyncMock,
        ):
            response = await client.delete(f"/feedback/golden-examples/{ge.id}")
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_removes_from_db(self, admin_client):
        client, session, _ = admin_client
        ge = _make_golden_example()
        session.add(ge)
        await session.commit()
        await session.refresh(ge)
        ge_id = ge.id

        with patch(
            "src.api.services.golden_example_service.GoldenExampleService._delete_from_qdrant",
            new_callable=AsyncMock,
        ):
            await client.delete(f"/feedback/golden-examples/{ge_id}")

        session.expire_all()
        result = await session.execute(
            select(GoldenExample).where(GoldenExample.id == ge_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_not_found(self, admin_client):
        client, _, _ = admin_client
        response = await client.delete(f"/feedback/golden-examples/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_no_permission(self, no_perms_client):
        client, _, _ = no_perms_client
        response = await client.delete(f"/feedback/golden-examples/{uuid4()}")
        assert response.status_code == 403


# ============================================================
# Unauthenticated access — all endpoints
# ============================================================


class TestFeedbackUnauthenticated:
    """All feedback endpoints reject unauthenticated requests."""

    @pytest.mark.asyncio
    async def test_submit(self, client):
        assert (await client.post("/feedback/", json={
            "message_id": str(uuid4()), "feedback_type": "positive",
        })).status_code == 403

    @pytest.mark.asyncio
    async def test_get_for_message(self, client):
        assert (await client.get(f"/feedback/message/{uuid4()}")).status_code == 403

    @pytest.mark.asyncio
    async def test_admin_list(self, client):
        assert (await client.get("/feedback/admin/list")).status_code == 403

    @pytest.mark.asyncio
    async def test_admin_stats(self, client):
        assert (await client.get("/feedback/admin/stats")).status_code == 403

    @pytest.mark.asyncio
    async def test_admin_settings_get(self, client):
        assert (await client.get("/feedback/admin/settings")).status_code == 403

    @pytest.mark.asyncio
    async def test_admin_settings_put(self, client):
        assert (await client.put("/feedback/admin/settings", json={})).status_code == 403

    @pytest.mark.asyncio
    async def test_admin_detail(self, client):
        assert (await client.get(f"/feedback/admin/{uuid4()}")).status_code == 403

    @pytest.mark.asyncio
    async def test_admin_resolve(self, client):
        assert (await client.post(f"/feedback/admin/{uuid4()}/resolve", json={})).status_code == 403

    @pytest.mark.asyncio
    async def test_admin_dismiss(self, client):
        assert (await client.post(f"/feedback/admin/{uuid4()}/dismiss", json={})).status_code == 403

    @pytest.mark.asyncio
    async def test_admin_restore(self, client):
        assert (await client.post(f"/feedback/admin/{uuid4()}/restore")).status_code == 403

    @pytest.mark.asyncio
    async def test_admin_delete(self, client):
        assert (await client.delete(f"/feedback/admin/{uuid4()}")).status_code == 403

    @pytest.mark.asyncio
    async def test_admin_generate(self, client):
        assert (await client.post(f"/feedback/admin/{uuid4()}/generate-response")).status_code == 403

    @pytest.mark.asyncio
    async def test_golden_list(self, client):
        assert (await client.get("/feedback/golden-examples/")).status_code == 403

    @pytest.mark.asyncio
    async def test_golden_get(self, client):
        assert (await client.get(f"/feedback/golden-examples/{uuid4()}")).status_code == 403

    @pytest.mark.asyncio
    async def test_golden_create(self, client):
        assert (await client.post("/feedback/golden-examples/", json={
            "original_query": "Q", "golden_response": "A",
        })).status_code == 403

    @pytest.mark.asyncio
    async def test_golden_update(self, client):
        assert (await client.put(f"/feedback/golden-examples/{uuid4()}", json={
            "golden_response": "A",
        })).status_code == 403

    @pytest.mark.asyncio
    async def test_golden_delete(self, client):
        assert (await client.delete(f"/feedback/golden-examples/{uuid4()}")).status_code == 403


# ============================================================
# Edge cases & hardening — Feedback endpoints
# ============================================================


class TestFeedbackEdgeCases:
    """Edge cases that attempt to break the feedback system."""

    @pytest.mark.asyncio
    async def test_submit_feedback_very_long_reason(self, admin_client):
        """Submit feedback with very long reason string."""
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)

        long_reason = "x" * 5000
        response = await client.post("/feedback/", json={
            "message_id": str(msg.id),
            "feedback_type": "negative",
            "reason": long_reason,
        })
        assert response.status_code == 201
        assert response.json()["reason"] == long_reason

    @pytest.mark.asyncio
    async def test_submit_feedback_special_chars_in_reason(self, admin_client):
        """Submit feedback with special characters, XSS payloads in reason."""
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)

        xss_reason = "<script>alert('xss')</script> & \"quotes\" 日本語"
        response = await client.post("/feedback/", json={
            "message_id": str(msg.id),
            "feedback_type": "negative",
            "reason": xss_reason,
        })
        assert response.status_code == 201
        assert response.json()["reason"] == xss_reason

    @pytest.mark.asyncio
    async def test_submit_feedback_null_reason(self, admin_client):
        """Submit feedback with explicit null reason."""
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)

        with patch(
            "src.api.services.golden_example_service.GoldenExampleService._embed_example",
            new_callable=AsyncMock, return_value="p",
        ):
            response = await client.post("/feedback/", json={
                "message_id": str(msg.id),
                "feedback_type": "positive",
                "reason": None,
            })
        assert response.status_code == 201
        assert response.json()["reason"] is None


class TestFeedbackStateTransitions:
    """Tests for invalid state transitions."""

    @pytest.mark.asyncio
    async def test_dismiss_then_dismiss_again_fails(self, admin_client):
        """Cannot dismiss already-dismissed feedback."""
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id, status="pending")
        session.add(fb)
        await session.commit()
        await session.refresh(fb)

        # First dismiss
        r1 = await client.post(f"/feedback/admin/{fb.id}/dismiss", json={})
        assert r1.status_code == 200

        # Second dismiss
        r2 = await client.post(f"/feedback/admin/{fb.id}/dismiss", json={})
        assert r2.status_code == 400

    @pytest.mark.asyncio
    async def test_resolve_then_restore_fails(self, admin_client):
        """Cannot restore reviewed feedback (only dismissed can be restored)."""
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id, feedback_type="positive")
        session.add(fb)
        await session.commit()
        await session.refresh(fb)

        # Resolve
        with patch(
            "src.api.services.golden_example_service.GoldenExampleService._embed_example",
            new_callable=AsyncMock, return_value="point",
        ):
            r1 = await client.post(f"/feedback/admin/{fb.id}/resolve", json={})
        assert r1.status_code == 200

        # Try to restore
        r2 = await client.post(f"/feedback/admin/{fb.id}/restore")
        assert r2.status_code == 400

    @pytest.mark.asyncio
    async def test_dismiss_then_restore_then_resolve(self, admin_client):
        """Full cycle: dismiss -> restore -> resolve."""
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id, feedback_type="positive")
        session.add(fb)
        await session.commit()
        await session.refresh(fb)

        # Dismiss
        r1 = await client.post(f"/feedback/admin/{fb.id}/dismiss", json={})
        assert r1.status_code == 200
        assert r1.json()["status"] == "dismissed"

        # Restore
        r2 = await client.post(f"/feedback/admin/{fb.id}/restore")
        assert r2.status_code == 200
        assert r2.json()["status"] == "pending"

        # Resolve
        with patch(
            "src.api.services.golden_example_service.GoldenExampleService._embed_example",
            new_callable=AsyncMock, return_value="point",
        ):
            r3 = await client.post(f"/feedback/admin/{fb.id}/resolve", json={})
        assert r3.status_code == 200
        assert r3.json()["status"] == "reviewed"


class TestFeedbackDeleteVerification:
    """Verify delete truly removes data."""

    @pytest.mark.asyncio
    async def test_delete_feedback_then_submit_new(self, admin_client):
        """After deleting feedback, user can submit new feedback for same message."""
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        fb = _make_feedback(msg.id, user_id, feedback_type="negative")
        session.add(fb)
        await session.commit()
        await session.refresh(fb)

        # Delete
        await client.delete(f"/feedback/admin/{fb.id}")

        # Submit new feedback for same message
        with patch(
            "src.api.services.golden_example_service.GoldenExampleService._embed_example",
            new_callable=AsyncMock, return_value="p",
        ):
            response = await client.post("/feedback/", json={
                "message_id": str(msg.id),
                "feedback_type": "positive",
            })
        assert response.status_code == 201


class TestAdminListEdgeCases:
    """Edge cases for admin feedback list."""

    @pytest.mark.asyncio
    async def test_list_offset_beyond_total(self, admin_client):
        """Offset beyond total returns empty list."""
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        session.add(_make_feedback(msg.id, user_id))
        await session.commit()

        response = await client.get("/feedback/admin/list?limit=10&offset=100")
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_list_combined_filters(self, admin_client):
        """Combine status + type filters."""
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id)
        _, msg2 = await _seed_extra_message(session, user_id)
        _, msg3 = await _seed_extra_message(session, user_id, human="Q3", bot="A3")
        session.add(_make_feedback(msg.id, user_id, feedback_type="negative", status="pending"))
        session.add(_make_feedback(msg2.id, user_id, feedback_type="positive", status="pending"))
        session.add(_make_feedback(msg3.id, user_id, feedback_type="negative", status="dismissed"))
        await session.commit()

        response = await client.get("/feedback/admin/list?status=pending&type=negative")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["feedback_type"] == "negative"
        assert data["items"][0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_search_no_results(self, admin_client):
        """Search with no matching results returns empty."""
        client, session, user_id = admin_client
        _, _, msg = await _seed(session, user_id, human="VPN issue", bot="Restart")
        session.add(_make_feedback(msg.id, user_id))
        await session.commit()

        response = await client.get("/feedback/admin/list?search=xyznonexistent")
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0


class TestGoldenExampleEdgeCases:
    """Edge cases for golden example CRUD."""

    @pytest.mark.asyncio
    async def test_create_golden_example_very_long_content(self, admin_client):
        """Create golden example with very long query and response."""
        client, session, user_id = admin_client
        session.add(_make_user(user_id))
        await session.commit()

        long_q = "Question " * 1000
        long_r = "Response " * 1000
        with patch(
            "src.api.services.golden_example_service.GoldenExampleService._embed_example",
            new_callable=AsyncMock, return_value="p",
        ):
            response = await client.post("/feedback/golden-examples/", json={
                "original_query": long_q,
                "golden_response": long_r,
            })
        assert response.status_code == 201
        assert response.json()["original_query"] == long_q

    @pytest.mark.asyncio
    async def test_update_golden_example_toggle_active_twice(self, admin_client):
        """Toggle is_active off then on."""
        client, session, _ = admin_client
        ge = _make_golden_example(is_active=True)
        session.add(ge)
        await session.commit()
        await session.refresh(ge)

        # Deactivate
        r1 = await client.put(f"/feedback/golden-examples/{ge.id}", json={
            "is_active": False,
        })
        assert r1.status_code == 200
        assert r1.json()["is_active"] is False

        # Reactivate
        r2 = await client.put(f"/feedback/golden-examples/{ge.id}", json={
            "is_active": True,
        })
        assert r2.status_code == 200
        assert r2.json()["is_active"] is True

    @pytest.mark.asyncio
    async def test_list_golden_examples_combined_filters(self, admin_client):
        """Combine source_type and is_active filters."""
        client, session, _ = admin_client
        session.add(_make_golden_example(source_type="manual", is_active=True))
        session.add(_make_golden_example(source_type="manual", is_active=False))
        session.add(_make_golden_example(source_type="positive", is_active=True))
        await session.commit()

        response = await client.get(
            "/feedback/golden-examples/?source_type=manual&is_active=true"
        )
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["source_type"] == "manual"
        assert data["items"][0]["is_active"] is True

from src.api.services.feedback_service import FeedbackService

async def _setup_feedback_context(session):
    """Create user, chat, message for feedback testing. Returns (user, chat, message)."""
    user = User(email=f"fb_{uuid4().hex[:8]}@test.com", is_active=True)
    session.add(user)
    await session.flush()
    chat = Chat(user_id=user.id, title="FB Chat")
    session.add(chat)
    await session.flush()
    msg = Message(chat_id=chat.id, human="Question?", bot="Answer.")
    session.add(msg)
    await session.commit()
    await session.refresh(user)
    await session.refresh(chat)
    await session.refresh(msg)
    return user, chat, msg


class TestFeedbackServiceSettings:
    """Tests for get_feedback_settings()."""

    @pytest.mark.asyncio
    async def test_defaults_when_no_settings(self, test_session):
        svc = FeedbackService(test_session)
        settings = await svc.get_feedback_settings()
        assert settings["auto_approve_positive"] is True
        assert settings["auto_approve_negative"] is False

    @pytest.mark.asyncio
    async def test_reads_from_db(self, test_session):
        user = User(email="s@test.com", is_active=True)
        test_session.add(user)
        await test_session.flush()
        setting = Setting(
            user_id=user.id, deny_words="", langfuse_enabled=False,
            change_type="create",
            feedback_auto_approve_positive=False,
            feedback_auto_approve_negative=True,
        )
        test_session.add(setting)
        await test_session.commit()

        svc = FeedbackService(test_session)
        settings = await svc.get_feedback_settings()
        assert settings["auto_approve_positive"] is False
        assert settings["auto_approve_negative"] is True


class TestFeedbackServiceCreate:
    """Tests for create_feedback()."""

    @pytest.mark.asyncio
    async def test_create_positive(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        # Disable auto-approve so we don't need to mock golden example creation
        setting = Setting(
            user_id=user.id, deny_words="", langfuse_enabled=False,
            change_type="create",
            feedback_auto_approve_positive=False,
        )
        test_session.add(setting)
        await test_session.commit()

        svc = FeedbackService(test_session)
        fb, ge, _ = await svc.create_feedback(msg.id, user.id, "positive")
        assert fb.feedback_type == "positive"
        assert fb.status == "pending"
        assert ge is None

    @pytest.mark.asyncio
    async def test_create_negative_pending(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)

        fb, ge, _ = await svc.create_feedback(msg.id, user.id, "negative")
        assert fb.feedback_type == "negative"
        assert fb.status == "pending"  # default auto_approve_negative=False
        assert ge is None

    @pytest.mark.asyncio
    async def test_create_duplicate_raises(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)

        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative")
        with pytest.raises(ValueError, match="already submitted"):
            await svc.create_feedback(msg.id, user.id, "positive")

    @pytest.mark.asyncio
    async def test_create_message_not_found(self, test_session):
        user, _, _ = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)
        with pytest.raises(ValueError, match="not found"):
            await svc.create_feedback(uuid4(), user.id, "positive")

    @pytest.mark.asyncio
    async def test_create_wrong_user_raises(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        other_user = User(email="other@test.com", is_active=True)
        test_session.add(other_user)
        await test_session.commit()
        await test_session.refresh(other_user)

        svc = FeedbackService(test_session)
        with pytest.raises(ValueError, match="not found"):
            await svc.create_feedback(msg.id, other_user.id, "positive")


class TestFeedbackServiceUpdate:
    """Tests for update_feedback()."""

    @pytest.mark.asyncio
    async def test_update_pending(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative")

        updated = await svc.update_feedback(fb.id, user.id, reason="Updated reason")
        assert updated.reason == "Updated reason"

    @pytest.mark.asyncio
    async def test_update_feedback_type(self, test_session):
        """Updating feedback_type branch (line 159)."""
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative")

        updated = await svc.update_feedback(
            fb.id, user.id, feedback_type="positive", reason="actually good"
        )
        assert updated.feedback_type == "positive"
        assert updated.reason == "actually good"

    @pytest.mark.asyncio
    async def test_update_wrong_user_raises(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        other = User(email="other2@test.com", is_active=True)
        test_session.add(other)
        await test_session.commit()
        await test_session.refresh(other)

        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative")

        with pytest.raises(ValueError, match="your own"):
            await svc.update_feedback(fb.id, other.id, reason="hack")

    @pytest.mark.asyncio
    async def test_update_processed_raises(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)

        # Create negative pending, then mark as reviewed manually
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative")
        fb.status = "reviewed"
        await test_session.commit()
        await test_session.refresh(fb)

        with pytest.raises(ValueError, match="already been processed"):
            await svc.update_feedback(fb.id, user.id, reason="too late")

    @pytest.mark.asyncio
    async def test_update_not_found(self, test_session):
        svc = FeedbackService(test_session)
        result = await svc.update_feedback(uuid4(), uuid4())
        assert result is None


class TestFeedbackServiceDismissRestore:
    """Tests for dismiss_feedback and restore_feedback."""

    @pytest.mark.asyncio
    async def test_dismiss(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative")

        dismissed = await svc.dismiss_feedback(fb.id, user.id, reason="Not useful")
        assert dismissed.status == "dismissed"
        assert "[Dismissed:" in dismissed.reason

    @pytest.mark.asyncio
    async def test_dismiss_not_found(self, test_session):
        svc = FeedbackService(test_session)
        with pytest.raises(ValueError, match="not found"):
            await svc.dismiss_feedback(uuid4(), uuid4())

    @pytest.mark.asyncio
    async def test_restore(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative", reason="Original")

        await svc.dismiss_feedback(fb.id, user.id, reason="Nah")
        restored = await svc.restore_feedback(fb.id)
        assert restored.status == "pending"
        assert restored.reviewed_by is None

    @pytest.mark.asyncio
    async def test_restore_non_dismissed_raises(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative")

        with pytest.raises(ValueError, match="Only dismissed"):
            await svc.restore_feedback(fb.id)


class TestFeedbackServiceDelete:
    """Tests for delete_feedback."""

    @pytest.mark.asyncio
    async def test_delete_success(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative")

        result = await svc.delete_feedback(fb.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_not_found(self, test_session):
        svc = FeedbackService(test_session)
        result = await svc.delete_feedback(uuid4())
        assert result is False


class TestFeedbackServiceStats:
    """Tests for get_feedback_stats."""

    @pytest.mark.asyncio
    async def test_empty_stats(self, test_session):
        svc = FeedbackService(test_session)
        stats = await svc.get_feedback_stats()
        assert stats["total_feedback"] == 0
        assert stats["positive_count"] == 0
        assert stats["negative_count"] == 0

    @pytest.mark.asyncio
    async def test_counts_correct(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        # Disable auto-approve so we don't need golden example creation
        setting = Setting(
            user_id=user.id, deny_words="", langfuse_enabled=False,
            change_type="create",
            feedback_auto_approve_positive=False,
        )
        test_session.add(setting)

        msg2 = Message(chat_id=chat.id, human="Q2", bot="A2")
        test_session.add(msg2)
        await test_session.commit()
        await test_session.refresh(msg2)

        svc = FeedbackService(test_session)
        await svc.create_feedback(msg.id, user.id, "negative")
        await svc.create_feedback(msg2.id, user.id, "positive")

        stats = await svc.get_feedback_stats()
        assert stats["total_feedback"] == 2
        assert stats["positive_count"] == 1
        assert stats["negative_count"] == 1


class TestFeedbackServiceListFeedback:
    """Tests for list_feedback."""

    @pytest.mark.asyncio
    async def test_list_empty(self, test_session):
        svc = FeedbackService(test_session)
        items, total = await svc.list_feedback()
        assert items == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_returns_items(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        setting = Setting(
            user_id=user.id, deny_words="", langfuse_enabled=False,
            change_type="create",
            feedback_auto_approve_positive=False,
        )
        test_session.add(setting)
        await test_session.commit()

        svc = FeedbackService(test_session)
        await svc.create_feedback(msg.id, user.id, "negative", reason="Bad answer")

        items, total = await svc.list_feedback()
        assert total == 1
        assert len(items) == 1
        item = items[0]
        assert item["feedback_type"] == "negative"
        assert item["reason"] == "Bad answer"
        assert item["user_email"] is not None
        assert item["original_query"] == msg.human

    @pytest.mark.asyncio
    async def test_list_with_status_filter(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        msg2 = Message(chat_id=chat.id, human="Q2", bot="A2")
        test_session.add(msg2)
        await test_session.commit()
        await test_session.refresh(msg2)

        svc = FeedbackService(test_session)
        fb1, _, _ = await svc.create_feedback(msg.id, user.id, "negative")
        fb2, _, _ = await svc.create_feedback(msg2.id, user.id, "negative")
        await svc.dismiss_feedback(fb1.id, user.id)

        items, total = await svc.list_feedback(status_filter="dismissed")
        assert total == 1
        assert items[0]["status"] == "dismissed"

    @pytest.mark.asyncio
    async def test_list_with_type_filter(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        setting = Setting(
            user_id=user.id, deny_words="", langfuse_enabled=False,
            change_type="create", feedback_auto_approve_positive=False,
        )
        test_session.add(setting)
        msg2 = Message(chat_id=chat.id, human="Q2", bot="A2")
        test_session.add(msg2)
        await test_session.commit()
        await test_session.refresh(msg2)

        svc = FeedbackService(test_session)
        await svc.create_feedback(msg.id, user.id, "negative")
        await svc.create_feedback(msg2.id, user.id, "positive")

        items, total = await svc.list_feedback(type_filter="positive")
        assert total == 1
        assert items[0]["feedback_type"] == "positive"

    @pytest.mark.asyncio
    async def test_list_with_search(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)
        await svc.create_feedback(msg.id, user.id, "negative", reason="terrible answer")

        items, total = await svc.list_feedback(search="terrible")
        assert total == 1

    @pytest.mark.asyncio
    async def test_list_pagination(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        setting = Setting(
            user_id=user.id, deny_words="", langfuse_enabled=False,
            change_type="create", feedback_auto_approve_positive=False,
        )
        test_session.add(setting)
        msgs = []
        for i in range(3):
            m = Message(chat_id=chat.id, human=f"Q{i}", bot=f"A{i}")
            test_session.add(m)
            msgs.append(m)
        await test_session.commit()
        for m in msgs:
            await test_session.refresh(m)

        svc = FeedbackService(test_session)
        for m in msgs:
            await svc.create_feedback(m.id, user.id, "negative")

        items, total = await svc.list_feedback(limit=2, offset=0)
        assert total == 3
        assert len(items) == 2

        items2, total2 = await svc.list_feedback(limit=2, offset=2)
        assert total2 == 3
        assert len(items2) == 1

    @pytest.mark.asyncio
    async def test_list_with_reviewer(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative")
        await svc.dismiss_feedback(fb.id, user.id, reason="dismiss it")

        items, total = await svc.list_feedback()
        assert total == 1
        assert items[0]["reviewed_by"] is not None
        assert items[0]["reviewer_email"] is not None


class TestFeedbackServiceGetWithContext:
    """Tests for get_feedback_with_context."""

    @pytest.mark.asyncio
    async def test_get_with_context(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative", reason="bad")

        result = await svc.get_feedback_with_context(fb.id)
        assert result is not None
        assert result["feedback_type"] == "negative"
        assert result["reason"] == "bad"
        assert result["original_query"] == msg.human
        assert result["original_response"] == msg.bot
        assert result["has_golden_example"] is False

    @pytest.mark.asyncio
    async def test_get_with_context_not_found(self, test_session):
        svc = FeedbackService(test_session)
        result = await svc.get_feedback_with_context(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_with_context_reviewed(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative")
        await svc.dismiss_feedback(fb.id, user.id)

        result = await svc.get_feedback_with_context(fb.id)
        assert result["reviewed_by"] is not None
        assert result["reviewer_email"] is not None


class TestFeedbackServiceResolve:
    """Tests for resolve_feedback."""

    @pytest.mark.asyncio
    async def test_resolve_positive(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        # Disable auto-approve so create_feedback doesn't try to embed
        setting = Setting(
            user_id=user.id, deny_words="", langfuse_enabled=False,
            change_type="create", feedback_auto_approve_positive=False,
        )
        test_session.add(setting)
        await test_session.commit()

        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "positive")

        from src.api.db.models.golden_example import GoldenExample
        ge = GoldenExample(
            original_query=msg.human,
            original_response=msg.bot,
            golden_response=msg.bot,
            feedback_id=fb.id,
            source_type="positive",
            approval_type="manual",
        )
        test_session.add(ge)
        await test_session.flush()

        with patch.object(svc, "_create_golden_example_from_feedback", new_callable=AsyncMock, return_value=ge):
            result_fb, result_ge = await svc.resolve_feedback(fb.id, user.id)

        assert result_fb.status == "reviewed"
        assert result_fb.reviewed_by == user.id

    @pytest.mark.asyncio
    async def test_resolve_negative_requires_golden(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative")

        with pytest.raises(ValueError, match="Golden response is required"):
            await svc.resolve_feedback(fb.id, user.id)

    @pytest.mark.asyncio
    async def test_resolve_negative_with_golden(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative")

        from src.api.db.models.golden_example import GoldenExample
        ge = GoldenExample(
            original_query=msg.human,
            original_response=msg.bot,
            golden_response="Better answer",
            feedback_id=fb.id,
            source_type="negative",
            approval_type="manual",
        )
        test_session.add(ge)
        await test_session.flush()

        with patch.object(svc, "_create_golden_example_from_feedback", new_callable=AsyncMock, return_value=ge):
            result_fb, result_ge = await svc.resolve_feedback(
                fb.id, user.id, golden_response="Better answer"
            )

        assert result_fb.status == "reviewed"

    @pytest.mark.asyncio
    async def test_resolve_not_found(self, test_session):
        svc = FeedbackService(test_session)
        with pytest.raises(ValueError, match="not found"):
            await svc.resolve_feedback(uuid4(), uuid4())

    @pytest.mark.asyncio
    async def test_resolve_message_not_found(self, test_session):
        """Resolve raises when associated message is not found (line 338)."""
        user, chat, msg = await _setup_feedback_context(test_session)
        # Disable auto-approve to avoid golden example creation (circular import)
        setting = Setting(
            user_id=user.id, deny_words="", langfuse_enabled=False,
            change_type="create",
            feedback_auto_approve_positive=False,
        )
        test_session.add(setting)
        await test_session.commit()

        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "positive")

        with patch.object(svc, "get_message_with_context", new_callable=AsyncMock, return_value=None):
            with pytest.raises(ValueError, match="Associated message not found"):
                await svc.resolve_feedback(fb.id, user.id)

    @pytest.mark.asyncio
    async def test_resolve_already_processed(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative")
        fb.status = "reviewed"
        await test_session.commit()
        await test_session.refresh(fb)

        with pytest.raises(ValueError, match="already been processed"):
            await svc.resolve_feedback(fb.id, user.id, golden_response="x")

    @pytest.mark.asyncio
    async def test_dismiss_already_processed(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative")
        fb.status = "reviewed"
        await test_session.commit()
        await test_session.refresh(fb)

        with pytest.raises(ValueError, match="already been processed"):
            await svc.dismiss_feedback(fb.id, user.id)

    @pytest.mark.asyncio
    async def test_dismiss_without_reason(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative")

        dismissed = await svc.dismiss_feedback(fb.id, user.id)
        assert dismissed.status == "dismissed"

    @pytest.mark.asyncio
    async def test_dismiss_no_existing_reason(self, test_session):
        """Dismiss with reason when feedback has no existing reason."""
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative")

        dismissed = await svc.dismiss_feedback(fb.id, user.id, reason="Not useful")
        assert "[Dismissed: Not useful]" in dismissed.reason

    @pytest.mark.asyncio
    async def test_restore_cleans_dismiss_reason(self, test_session):
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative", reason="Original text")

        await svc.dismiss_feedback(fb.id, user.id, reason="Nah")
        restored = await svc.restore_feedback(fb.id)
        assert restored.reason == "Original text"
        assert "[Dismissed:" not in (restored.reason or "")

    @pytest.mark.asyncio
    async def test_restore_not_found(self, test_session):
        svc = FeedbackService(test_session)
        with pytest.raises(ValueError, match="not found"):
            await svc.restore_feedback(uuid4())

    @pytest.mark.asyncio
    async def test_delete_with_golden_example(self, test_session):
        """Delete feedback that has an associated golden example."""
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative")

        from src.api.db.models.golden_example import GoldenExample
        ge = GoldenExample(
            original_query=msg.human,
            original_response=msg.bot,
            golden_response="Better",
            feedback_id=fb.id,
            source_type="negative",
            approval_type="manual",
        )
        test_session.add(ge)
        await test_session.commit()

        result = await svc.delete_feedback(fb.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_with_golden_and_qdrant(self, test_session):
        """Delete feedback with golden example that has qdrant_point_id."""
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative")

        from src.api.db.models.golden_example import GoldenExample
        ge = GoldenExample(
            original_query=msg.human,
            original_response=msg.bot,
            golden_response="Better",
            feedback_id=fb.id,
            source_type="negative",
            approval_type="manual",
            qdrant_point_id="point-123",
        )
        test_session.add(ge)
        await test_session.commit()

        with patch(
            "src.api.services.golden_example_service.GoldenExampleService._delete_from_qdrant",
            new_callable=AsyncMock,
        ):
            result = await svc.delete_feedback(fb.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_with_qdrant_failure(self, test_session):
        """Qdrant deletion failure doesn't prevent feedback deletion."""
        user, chat, msg = await _setup_feedback_context(test_session)
        svc = FeedbackService(test_session)
        fb, _, _ = await svc.create_feedback(msg.id, user.id, "negative")

        from src.api.db.models.golden_example import GoldenExample
        ge = GoldenExample(
            original_query=msg.human,
            original_response=msg.bot,
            golden_response="Better",
            feedback_id=fb.id,
            source_type="negative",
            approval_type="manual",
            qdrant_point_id="point-456",
        )
        test_session.add(ge)
        await test_session.commit()

        with patch(
            "src.api.services.golden_example_service.GoldenExampleService._delete_from_qdrant",
            new_callable=AsyncMock,
            side_effect=RuntimeError("qdrant down"),
        ):
            result = await svc.delete_feedback(fb.id)
        assert result is True

class TestFeedbackRouterErrorPaths:
    """Tests for exception handlers in feedback router endpoints."""

    @pytest.mark.asyncio
    async def test_submit_invalid_message_id(self, admin_client):
        """Invalid UUID in message_id returns 400."""
        client, _, _ = admin_client
        response = await client.post("/feedback/", json={
            "message_id": "not-a-uuid",
            "feedback_type": "positive",
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_submit_value_error(self, admin_client):
        """ValueError in submit returns 400."""
        client, _, _ = admin_client
        with patch(
            "src.api.services.feedback_service.FeedbackService.create_feedback",
            new_callable=AsyncMock,
            side_effect=ValueError("Message not found"),
        ):
            response = await client.post("/feedback/", json={
                "message_id": str(uuid4()),
                "feedback_type": "positive",
            })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_submit_internal_error(self, admin_client):
        """Internal error in submit returns 500."""
        client, _, _ = admin_client
        with patch(
            "src.api.services.feedback_service.FeedbackService.create_feedback",
            new_callable=AsyncMock,
            side_effect=RuntimeError("unexpected"),
        ):
            response = await client.post("/feedback/", json={
                "message_id": str(uuid4()),
                "feedback_type": "positive",
            })
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_get_feedback_for_message_invalid_uuid(self, admin_client):
        """Invalid UUID returns None (not an error)."""
        client, _, _ = admin_client
        response = await client.get("/feedback/message/not-a-uuid")
        assert response.status_code == 200
        assert response.json() is None

    @pytest.mark.asyncio
    async def test_get_feedback_for_message_internal_error(self, admin_client):
        """Internal error in get_feedback_for_message returns 500."""
        client, _, _ = admin_client
        with patch(
            "src.api.services.feedback_service.FeedbackService.get_feedback_by_message",
            new_callable=AsyncMock,
            side_effect=RuntimeError("db error"),
        ):
            response = await client.get(f"/feedback/message/{uuid4()}")
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_list_feedback_internal_error(self, admin_client):
        """Internal error in list_feedback returns 500."""
        client, _, _ = admin_client
        with patch(
            "src.api.services.feedback_service.FeedbackService.list_feedback",
            new_callable=AsyncMock,
            side_effect=RuntimeError("query error"),
        ):
            response = await client.get("/feedback/admin/list")
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_get_stats_internal_error(self, admin_client):
        """Internal error in get_feedback_stats returns 500."""
        client, _, _ = admin_client
        with patch(
            "src.api.services.feedback_service.FeedbackService.get_feedback_stats",
            new_callable=AsyncMock,
            side_effect=RuntimeError("stats error"),
        ):
            response = await client.get("/feedback/admin/stats")
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_get_settings_internal_error(self, admin_client):
        """Internal error in get_feedback_settings returns 500."""
        client, _, _ = admin_client
        with patch(
            "src.api.services.feedback_service.FeedbackService.get_feedback_settings",
            new_callable=AsyncMock,
            side_effect=RuntimeError("settings error"),
        ):
            response = await client.get("/feedback/admin/settings")
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_update_settings_no_settings(self, admin_client):
        """Update settings when no settings exist returns 404."""
        client, _, _ = admin_client
        with patch(
            "src.api.services.settings_service.SettingsService.get_latest_setting",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await client.put("/feedback/admin/settings", json={
                "auto_approve_positive": True,
            })
        # Should get 404 or 500 depending on error propagation
        assert response.status_code in (404, 500)

    @pytest.mark.asyncio
    async def test_get_details_internal_error(self, admin_client):
        """Internal error in get_feedback_details returns 500."""
        client, _, _ = admin_client
        with patch(
            "src.api.services.feedback_service.FeedbackService.get_feedback_with_context",
            new_callable=AsyncMock,
            side_effect=RuntimeError("context error"),
        ):
            response = await client.get(f"/feedback/admin/{uuid4()}")
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_resolve_internal_error(self, admin_client):
        """Internal error in resolve_feedback returns 500."""
        client, _, _ = admin_client
        with patch(
            "src.api.services.feedback_service.FeedbackService.resolve_feedback",
            new_callable=AsyncMock,
            side_effect=RuntimeError("resolve error"),
        ):
            response = await client.post(f"/feedback/admin/{uuid4()}/resolve", json={
                "golden_response": "better",
            })
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_dismiss_internal_error(self, admin_client):
        """Internal error in dismiss_feedback returns 500."""
        client, _, _ = admin_client
        with patch(
            "src.api.services.feedback_service.FeedbackService.dismiss_feedback",
            new_callable=AsyncMock,
            side_effect=RuntimeError("dismiss error"),
        ):
            response = await client.post(f"/feedback/admin/{uuid4()}/dismiss", json={
                "reason": "not relevant",
            })
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_restore_internal_error(self, admin_client):
        """Internal error in restore_feedback returns 500."""
        client, _, _ = admin_client
        with patch(
            "src.api.services.feedback_service.FeedbackService.restore_feedback",
            new_callable=AsyncMock,
            side_effect=RuntimeError("restore error"),
        ):
            response = await client.post(f"/feedback/admin/{uuid4()}/restore")
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_delete_internal_error(self, admin_client):
        """Internal error in delete_feedback returns 500."""
        client, _, _ = admin_client
        with patch(
            "src.api.services.feedback_service.FeedbackService.delete_feedback",
            new_callable=AsyncMock,
            side_effect=RuntimeError("delete error"),
        ):
            response = await client.delete(f"/feedback/admin/{uuid4()}")
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_generate_response_internal_error(self, admin_client):
        """Internal error in generate_golden_response returns 500."""
        client, _, _ = admin_client
        with patch(
            "src.api.services.feedback_service.FeedbackService.get_feedback_with_context",
            new_callable=AsyncMock,
            side_effect=RuntimeError("generate error"),
        ):
            response = await client.post(f"/feedback/admin/{uuid4()}/generate-response")
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_list_golden_examples_internal_error(self, admin_client):
        """Internal error in list_golden_examples returns 500."""
        client, _, _ = admin_client
        with patch(
            "src.api.services.golden_example_service.GoldenExampleService.list_examples",
            new_callable=AsyncMock,
            side_effect=RuntimeError("list error"),
        ):
            response = await client.get("/feedback/golden-examples/")
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_get_golden_example_internal_error(self, admin_client):
        """Internal error in get_golden_example returns 500."""
        client, _, _ = admin_client
        with patch(
            "src.api.services.golden_example_service.GoldenExampleService.get_by_id",
            new_callable=AsyncMock,
            side_effect=RuntimeError("get error"),
        ):
            response = await client.get(f"/feedback/golden-examples/{uuid4()}")
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_create_golden_example_internal_error(self, admin_client):
        """Internal error in create_golden_example returns 500."""
        client, _, _ = admin_client
        with patch(
            "src.api.services.golden_example_service.GoldenExampleService.create_example",
            new_callable=AsyncMock,
            side_effect=RuntimeError("create error"),
        ):
            response = await client.post("/feedback/golden-examples/", json={
                "original_query": "q",
                "golden_response": "r",
            })
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_update_golden_example_internal_error(self, admin_client):
        """Internal error in update_golden_example returns 500."""
        client, _, _ = admin_client
        with patch(
            "src.api.services.golden_example_service.GoldenExampleService.update_example",
            new_callable=AsyncMock,
            side_effect=RuntimeError("update error"),
        ):
            response = await client.put(f"/feedback/golden-examples/{uuid4()}", json={
                "golden_response": "updated",
            })
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_delete_golden_example_internal_error(self, admin_client):
        """Internal error in delete_golden_example returns 500."""
        client, _, _ = admin_client
        with patch(
            "src.api.services.golden_example_service.GoldenExampleService.delete_example",
            new_callable=AsyncMock,
            side_effect=RuntimeError("delete error"),
        ):
            response = await client.delete(f"/feedback/golden-examples/{uuid4()}")
        assert response.status_code == 500
