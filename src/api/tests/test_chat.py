"""Comprehensive tests for Chat CRUD endpoints (/chats).

Covers:
- List user chats (GET /)
- Get chat with messages (GET /messages/{chat_id})
- Rename chat (PUT /rename/{chat_id})
- Archive chat (DELETE /archive/{chat_id})
- Ownership enforcement (users can only access their own chats)
- Pagination
- Archived chat exclusion
- Unauthenticated access

Note: Prompt endpoints (POST /prompt, /prompt/stream) require heavy
mocking of LangGraph/LLM and are not covered here.
"""

import pytest
from datetime import datetime, UTC
from uuid import uuid4

from sqlalchemy.future import select

from src.api.db.models import Chat, Message


# ============================================================
# Helpers
# ============================================================

def _make_chat(user_id, *, title="Test Chat", archived_at=None, **kwargs):
    """Build a Chat ORM instance."""
    return Chat(user_id=user_id, title=title, archived_at=archived_at, **kwargs)


def _make_message(chat_id, *, human="Hello", bot="Hi there"):
    """Build a Message ORM instance."""
    return Message(chat_id=chat_id, human=human, bot=bot)


# ============================================================
# GET /chats/ — List user chats
# ============================================================


class TestListChats:
    """Tests for GET /chats/"""

    @pytest.mark.asyncio
    async def test_list_chats_empty(self, admin_client):
        """Returns empty list when user has no chats."""
        client, session, user_id = admin_client
        response = await client.get("/chats/")
        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["chats"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_chats_returns_user_chats(self, admin_client):
        """Returns all non-archived chats for the authenticated user."""
        client, session, user_id = admin_client
        session.add_all([
            _make_chat(user_id, title="Chat A"),
            _make_chat(user_id, title="Chat B"),
        ])
        await session.commit()

        response = await client.get("/chats/")
        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["total"] == 2
        titles = {c["title"] for c in data["chats"]}
        assert titles == {"Chat A", "Chat B"}

    @pytest.mark.asyncio
    async def test_list_chats_excludes_archived(self, admin_client):
        """Archived chats are excluded from the list."""
        client, session, user_id = admin_client
        session.add_all([
            _make_chat(user_id, title="Active"),
            _make_chat(user_id, title="Archived", archived_at=datetime.now(UTC).replace(tzinfo=None)),
        ])
        await session.commit()

        response = await client.get("/chats/")
        data = response.json()
        assert data["total"] == 1
        assert data["chats"][0]["title"] == "Active"

    @pytest.mark.asyncio
    async def test_list_chats_excludes_other_users(self, admin_client):
        """Does not return chats belonging to other users."""
        client, session, user_id = admin_client
        other_user_id = uuid4()
        session.add_all([
            _make_chat(user_id, title="Mine"),
            _make_chat(other_user_id, title="Theirs"),
        ])
        await session.commit()

        response = await client.get("/chats/")
        data = response.json()
        assert data["total"] == 1
        assert data["chats"][0]["title"] == "Mine"

    @pytest.mark.asyncio
    async def test_list_chats_pagination(self, admin_client):
        """Respects limit and offset parameters."""
        client, session, user_id = admin_client
        for i in range(5):
            session.add(_make_chat(user_id, title=f"Chat {i}"))
        await session.commit()

        response = await client.get("/chats/?limit=2&offset=0")
        data = response.json()
        assert len(data["chats"]) == 2
        assert data["total"] == 5
        assert data["has_more"] is True
        assert data["limit"] == 2
        assert data["offset"] == 0

    @pytest.mark.asyncio
    async def test_list_chats_pagination_last_page(self, admin_client):
        """Last page has has_more=false."""
        client, session, user_id = admin_client
        for i in range(3):
            session.add(_make_chat(user_id, title=f"Chat {i}"))
        await session.commit()

        response = await client.get("/chats/?limit=10&offset=0")
        data = response.json()
        assert len(data["chats"]) == 3
        assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_list_chats_response_format(self, admin_client):
        """Each chat has id, title, and updated_at fields."""
        client, session, user_id = admin_client
        session.add(_make_chat(user_id, title="Format Test"))
        await session.commit()

        response = await client.get("/chats/")
        chat = response.json()["chats"][0]
        assert "id" in chat
        assert chat["title"] == "Format Test"
        assert "updated_at" in chat

    @pytest.mark.asyncio
    async def test_list_chats_unauthenticated(self, client):
        """Unauthenticated request is rejected."""
        response = await client.get("/chats/")
        assert response.status_code == 403


# ============================================================
# GET /chats/messages/{chat_id} — Get chat with messages
# ============================================================


class TestGetChatMessages:
    """Tests for GET /chats/messages/{chat_id}"""

    @pytest.mark.asyncio
    async def test_get_messages_success(self, admin_client):
        """Returns chat with its messages."""
        client, session, user_id = admin_client
        chat = _make_chat(user_id, title="My Chat")
        session.add(chat)
        await session.flush()

        msg = _make_message(chat.id, human="Hi", bot="Hello!")
        session.add(msg)
        await session.commit()
        await session.refresh(chat)

        response = await client.get(f"/chats/messages/{chat.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["title"] == "My Chat"
        assert len(data["messages"]) == 1
        assert data["messages"][0]["human"] == "Hi"
        assert data["messages"][0]["bot"] == "Hello!"

    @pytest.mark.asyncio
    async def test_get_messages_empty(self, admin_client):
        """Chat with no messages returns empty list."""
        client, session, user_id = admin_client
        chat = _make_chat(user_id, title="Empty Chat")
        session.add(chat)
        await session.commit()
        await session.refresh(chat)

        response = await client.get(f"/chats/messages/{chat.id}")
        data = response.json()
        assert data["error"] is False
        assert data["messages"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_get_messages_pagination(self, admin_client):
        """Respects limit and offset for messages."""
        client, session, user_id = admin_client
        chat = _make_chat(user_id)
        session.add(chat)
        await session.flush()

        for i in range(5):
            session.add(_make_message(chat.id, human=f"Q{i}", bot=f"A{i}"))
        await session.commit()
        await session.refresh(chat)

        response = await client.get(
            f"/chats/messages/{chat.id}?limit=2&offset=0"
        )
        data = response.json()
        assert len(data["messages"]) == 2
        assert data["total"] == 5
        assert data["has_more"] is True

    @pytest.mark.asyncio
    async def test_get_messages_not_found(self, admin_client):
        """Non-existent chat returns 404."""
        client, _, _ = admin_client
        response = await client.get(f"/chats/messages/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_messages_other_user(self, admin_client):
        """Cannot access chat belonging to another user."""
        client, session, user_id = admin_client
        other_chat = _make_chat(uuid4(), title="Other's Chat")
        session.add(other_chat)
        await session.commit()
        await session.refresh(other_chat)

        response = await client.get(f"/chats/messages/{other_chat.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_messages_archived_chat(self, admin_client):
        """Archived chat is not accessible."""
        client, session, user_id = admin_client
        chat = _make_chat(user_id, archived_at=datetime.now(UTC).replace(tzinfo=None))
        session.add(chat)
        await session.commit()
        await session.refresh(chat)

        response = await client.get(f"/chats/messages/{chat.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_messages_response_format(self, admin_client):
        """Response contains expected fields."""
        client, session, user_id = admin_client
        chat = _make_chat(user_id, title="Format")
        session.add(chat)
        await session.flush()
        session.add(_make_message(chat.id))
        await session.commit()
        await session.refresh(chat)

        response = await client.get(f"/chats/messages/{chat.id}")
        data = response.json()
        assert "id" in data
        assert "user_id" in data
        assert "title" in data
        assert "messages" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert "has_more" in data

        msg = data["messages"][0]
        assert "id" in msg
        assert "chat_id" in msg
        assert "human" in msg
        assert "bot" in msg
        assert "created_at" in msg

    @pytest.mark.asyncio
    async def test_get_messages_unauthenticated(self, client):
        """Unauthenticated request is rejected."""
        response = await client.get(f"/chats/messages/{uuid4()}")
        assert response.status_code == 403


# ============================================================
# PUT /chats/rename/{chat_id} — Rename chat
# ============================================================


class TestRenameChat:
    """Tests for PUT /chats/rename/{chat_id}"""

    @pytest.mark.asyncio
    async def test_rename_chat_success(self, admin_client):
        """Successfully renames a chat."""
        client, session, user_id = admin_client
        chat = _make_chat(user_id, title="Old Title")
        session.add(chat)
        await session.commit()
        await session.refresh(chat)

        response = await client.put(
            f"/chats/rename/{chat.id}",
            json={"title": "New Title"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["new_title"] == "New Title"

    @pytest.mark.asyncio
    async def test_rename_chat_persists(self, admin_client):
        """Renamed title is persisted in the database."""
        client, session, user_id = admin_client
        chat = _make_chat(user_id, title="Before")
        session.add(chat)
        await session.commit()
        await session.refresh(chat)
        chat_id = chat.id

        await client.put(
            f"/chats/rename/{chat_id}",
            json={"title": "After"},
        )

        session.expire_all()
        result = await session.execute(
            select(Chat).where(Chat.id == chat_id)
        )
        db_chat = result.scalar_one()
        assert db_chat.title == "After"

    @pytest.mark.asyncio
    async def test_rename_chat_not_found(self, admin_client):
        """Non-existent chat returns 404."""
        client, _, _ = admin_client
        response = await client.put(
            f"/chats/rename/{uuid4()}",
            json={"title": "New"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_rename_chat_other_user(self, admin_client):
        """Cannot rename another user's chat."""
        client, session, user_id = admin_client
        other_chat = _make_chat(uuid4(), title="Not Mine")
        session.add(other_chat)
        await session.commit()
        await session.refresh(other_chat)

        response = await client.put(
            f"/chats/rename/{other_chat.id}",
            json={"title": "Hacked"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_rename_chat_missing_title(self, admin_client):
        """Missing title field returns 422."""
        client, session, user_id = admin_client
        chat = _make_chat(user_id)
        session.add(chat)
        await session.commit()
        await session.refresh(chat)

        response = await client.put(
            f"/chats/rename/{chat.id}", json={}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_rename_chat_unauthenticated(self, client):
        """Unauthenticated request is rejected."""
        response = await client.put(
            f"/chats/rename/{uuid4()}",
            json={"title": "Test"},
        )
        assert response.status_code == 403


# ============================================================
# DELETE /chats/archive/{chat_id} — Archive chat
# ============================================================


class TestArchiveChat:
    """Tests for DELETE /chats/archive/{chat_id}"""

    @pytest.mark.asyncio
    async def test_archive_chat_success(self, admin_client):
        """Successfully archives a chat."""
        client, session, user_id = admin_client
        chat = _make_chat(user_id, title="To Archive")
        session.add(chat)
        await session.commit()
        await session.refresh(chat)

        response = await client.delete(f"/chats/archive/{chat.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["message"] == "Chat archived successfully"

    @pytest.mark.asyncio
    async def test_archive_chat_sets_archived_at(self, admin_client):
        """Archiving sets archived_at timestamp (soft delete)."""
        client, session, user_id = admin_client
        chat = _make_chat(user_id)
        session.add(chat)
        await session.commit()
        await session.refresh(chat)
        chat_id = chat.id

        await client.delete(f"/chats/archive/{chat_id}")

        session.expire_all()
        result = await session.execute(
            select(Chat).where(Chat.id == chat_id)
        )
        db_chat = result.scalar_one()
        assert db_chat.archived_at is not None

    @pytest.mark.asyncio
    async def test_archive_chat_excluded_from_list(self, admin_client):
        """Archived chat no longer appears in chat list."""
        client, session, user_id = admin_client
        chat = _make_chat(user_id, title="Will Vanish")
        session.add(chat)
        await session.commit()
        await session.refresh(chat)

        await client.delete(f"/chats/archive/{chat.id}")

        response = await client.get("/chats/")
        titles = [c["title"] for c in response.json()["chats"]]
        assert "Will Vanish" not in titles

    @pytest.mark.asyncio
    async def test_archive_chat_preserves_messages(self, admin_client):
        """Archiving does NOT delete messages."""
        client, session, user_id = admin_client
        chat = _make_chat(user_id)
        session.add(chat)
        await session.flush()
        msg = _make_message(chat.id, human="Preserved", bot="Still here")
        session.add(msg)
        await session.commit()
        await session.refresh(chat)
        await session.refresh(msg)
        msg_id = msg.id

        await client.delete(f"/chats/archive/{chat.id}")

        # Message should still exist in DB
        result = await session.execute(
            select(Message).where(Message.id == msg_id)
        )
        assert result.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_archive_chat_not_found(self, admin_client):
        """Non-existent chat returns error response."""
        client, _, _ = admin_client
        response = await client.delete(f"/chats/archive/{uuid4()}")
        # The archive endpoint catches HTTPException and returns error JSON
        data = response.json()
        assert data["error"] is True

    @pytest.mark.asyncio
    async def test_archive_chat_other_user(self, admin_client):
        """Cannot archive another user's chat."""
        client, session, user_id = admin_client
        other_chat = _make_chat(uuid4(), title="Not Mine")
        session.add(other_chat)
        await session.commit()
        await session.refresh(other_chat)

        response = await client.delete(f"/chats/archive/{other_chat.id}")
        data = response.json()
        assert data["error"] is True

    @pytest.mark.asyncio
    async def test_archive_chat_unauthenticated(self, client):
        """Unauthenticated request is rejected."""
        response = await client.delete(f"/chats/archive/{uuid4()}")
        assert response.status_code == 403


# ============================================================
# Edge cases & hardening — Chat endpoints
# ============================================================


class TestListChatsEdgeCases:
    """Boundary and edge case tests for GET /chats/"""

    @pytest.mark.asyncio
    async def test_list_chats_offset_beyond_total(self, admin_client):
        """Offset greater than total returns empty list."""
        client, session, user_id = admin_client
        session.add(_make_chat(user_id, title="Only Chat"))
        await session.commit()

        response = await client.get("/chats/?limit=10&offset=100")
        data = response.json()
        assert data["error"] is False
        assert data["chats"] == []
        assert data["total"] == 1
        assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_list_chats_large_limit(self, admin_client):
        """Large limit doesn't cause issues."""
        client, session, user_id = admin_client
        session.add(_make_chat(user_id, title="One"))
        await session.commit()

        response = await client.get("/chats/?limit=10000")
        data = response.json()
        assert data["error"] is False
        assert len(data["chats"]) == 1

    @pytest.mark.asyncio
    async def test_list_chats_ordering(self, admin_client):
        """Chats are ordered by updated_at descending (newest first)."""
        from datetime import timedelta
        client, session, user_id = admin_client
        now = datetime.now(UTC).replace(tzinfo=None)
        c1 = _make_chat(user_id, title="First", updated_at=now - timedelta(seconds=10))
        c2 = _make_chat(user_id, title="Second", updated_at=now)
        session.add_all([c1, c2])
        await session.commit()

        response = await client.get("/chats/")
        data = response.json()
        # Most recently updated should be first
        assert len(data["chats"]) == 2
        assert data["chats"][0]["title"] == "Second"


class TestRenameChatEdgeCases:
    """Edge cases for PUT /chats/rename/{chat_id}"""

    @pytest.mark.asyncio
    async def test_rename_archived_chat_succeeds(self, admin_client):
        """Rename endpoint does NOT filter by archived_at, so this succeeds.

        This documents current behavior — the rename endpoint doesn't check archived_at.
        """
        client, session, user_id = admin_client
        chat = _make_chat(user_id, title="Archived", archived_at=datetime.now(UTC).replace(tzinfo=None))
        session.add(chat)
        await session.commit()
        await session.refresh(chat)

        response = await client.put(
            f"/chats/rename/{chat.id}",
            json={"title": "Renamed Archived"},
        )
        # Current code does NOT filter by archived_at on rename
        assert response.status_code == 200
        assert response.json()["new_title"] == "Renamed Archived"

    @pytest.mark.asyncio
    async def test_rename_chat_empty_string_title(self, admin_client):
        """Rename chat with empty string title."""
        client, session, user_id = admin_client
        chat = _make_chat(user_id, title="Original")
        session.add(chat)
        await session.commit()
        await session.refresh(chat)

        response = await client.put(
            f"/chats/rename/{chat.id}",
            json={"title": ""},
        )
        # Depends on schema validation — might succeed or fail
        assert response.status_code in (200, 422)

    @pytest.mark.asyncio
    async def test_rename_chat_very_long_title(self, admin_client):
        """Rename chat with very long title."""
        client, session, user_id = admin_client
        chat = _make_chat(user_id, title="Short")
        session.add(chat)
        await session.commit()
        await session.refresh(chat)

        long_title = "x" * 1000
        response = await client.put(
            f"/chats/rename/{chat.id}",
            json={"title": long_title},
        )
        # Should succeed — DB column is String without length limit
        assert response.status_code == 200
        assert response.json()["new_title"] == long_title

    @pytest.mark.asyncio
    async def test_rename_chat_special_characters(self, admin_client):
        """Rename chat with special characters, unicode, emojis."""
        client, session, user_id = admin_client
        chat = _make_chat(user_id, title="Normal")
        session.add(chat)
        await session.commit()
        await session.refresh(chat)

        special = "Chat <script>alert('xss')</script> 日本語 🎉"
        response = await client.put(
            f"/chats/rename/{chat.id}",
            json={"title": special},
        )
        assert response.status_code == 200
        assert response.json()["new_title"] == special

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="SQLite raises StatementError on invalid UUID bind; PostgreSQL returns 404/422",
        strict=False,
    )
    async def test_rename_chat_invalid_uuid(self, admin_client):
        """Invalid chat_id UUID format returns an error."""
        client, _, _ = admin_client
        response = await client.put(
            "/chats/rename/not-a-uuid",
            json={"title": "Test"},
        )
        # PostgreSQL would return 404 or 422; SQLite crashes on UUID conversion
        assert response.status_code in (404, 422, 500)


class TestArchiveChatEdgeCases:
    """Edge cases for DELETE /chats/archive/{chat_id}"""

    @pytest.mark.asyncio
    async def test_archive_already_archived_chat(self, admin_client):
        """Archiving an already-archived chat should still succeed."""
        client, session, user_id = admin_client
        chat = _make_chat(user_id, title="Already Archived", archived_at=datetime.now(UTC).replace(tzinfo=None))
        session.add(chat)
        await session.commit()
        await session.refresh(chat)

        response = await client.delete(f"/chats/archive/{chat.id}")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_archive_chat_then_messages_inaccessible(self, admin_client):
        """After archiving, GET /messages/{chat_id} returns error."""
        client, session, user_id = admin_client
        chat = _make_chat(user_id, title="Will Archive")
        session.add(chat)
        await session.flush()
        session.add(_make_message(chat.id, human="Q", bot="A"))
        await session.commit()
        await session.refresh(chat)
        chat_id = chat.id

        await client.delete(f"/chats/archive/{chat_id}")

        response = await client.get(f"/chats/messages/{chat_id}")
        assert response.status_code == 404


class TestGetMessagesEdgeCases:
    """Edge cases for GET /chats/messages/{chat_id}"""

    @pytest.mark.asyncio
    async def test_get_messages_offset_beyond_total(self, admin_client):
        """Offset beyond total messages returns empty list."""
        client, session, user_id = admin_client
        chat = _make_chat(user_id)
        session.add(chat)
        await session.flush()
        session.add(_make_message(chat.id))
        await session.commit()
        await session.refresh(chat)

        response = await client.get(
            f"/chats/messages/{chat.id}?limit=10&offset=100"
        )
        data = response.json()
        assert data["error"] is False
        assert data["messages"] == []
        assert data["total"] == 1
        assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_get_messages_large_limit(self, admin_client):
        """Large limit doesn't cause issues."""
        client, session, user_id = admin_client
        chat = _make_chat(user_id)
        session.add(chat)
        await session.flush()
        session.add(_make_message(chat.id))
        await session.commit()
        await session.refresh(chat)

        response = await client.get(
            f"/chats/messages/{chat.id}?limit=99999"
        )
        data = response.json()
        assert data["error"] is False
        assert len(data["messages"]) == 1

    @pytest.mark.asyncio
    async def test_get_messages_cross_user_isolation(self, admin_client):
        """Cannot read messages from another user's chat, even with valid chat_id."""
        client, session, user_id = admin_client
        other_user = uuid4()
        other_chat = _make_chat(other_user, title="Private")
        session.add(other_chat)
        await session.flush()
        session.add(_make_message(other_chat.id, human="Secret", bot="Data"))
        await session.commit()
        await session.refresh(other_chat)

        response = await client.get(f"/chats/messages/{other_chat.id}")
        # Should not be able to see messages
        assert response.status_code == 404


# ============================================================
# _message_content_to_str — LLM-agnostic content normalization
# ============================================================


class TestMessageContentToStr:
    """Tests for normalizing AIMessageChunk content (OpenAI/Gemini str vs Anthropic list)."""

    def test_str_passthrough(self):
        from src.api.routers.chat import _message_content_to_str
        assert _message_content_to_str("hello") == "hello"
        assert _message_content_to_str("") == ""

    def test_none_returns_empty(self):
        from src.api.routers.chat import _message_content_to_str
        assert _message_content_to_str(None) == ""

    def test_anthropic_text_blocks(self):
        from src.api.routers.chat import _message_content_to_str
        content = [{"type": "text", "text": "Hi "}, {"type": "text", "text": "there"}]
        assert _message_content_to_str(content) == "Hi there"

    def test_anthropic_thinking_excluded(self):
        from src.api.routers.chat import _message_content_to_str
        content = [{"type": "thinking", "thinking": "internal"}, {"type": "text", "text": "Answer"}]
        assert _message_content_to_str(content) == "Answer"

    def test_other_type_coerced_to_str(self):
        from src.api.routers.chat import _message_content_to_str
        assert _message_content_to_str(123) == "123"
