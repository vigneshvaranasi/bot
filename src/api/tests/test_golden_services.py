"""Tests for GoldenExampleService and GoldenResponseGenerator.

Covers service-level logic with mocked Qdrant and LLM dependencies.
"""

import asyncio
import pytest
import sys
from uuid import uuid4
from unittest.mock import patch, AsyncMock, MagicMock

from src.api.db.models import GoldenExample, User
_copilot_mods = ["src.copilot", "src.copilot.config", "src.copilot.graph", "src.copilot.tools"]
_orig = {k: sys.modules.get(k) for k in _copilot_mods}
_needs_cleanup = not all(k in sys.modules for k in _copilot_mods)

if _needs_cleanup:
    _mock_config = MagicMock()
    _mock_config.QDRANT_URL = "http://localhost:6333"
    _mock_config.QDRANT_API_KEY = ""
    sys.modules["src.copilot"] = sys.modules.get("src.copilot") or MagicMock()
    sys.modules["src.copilot.config"] = sys.modules.get("src.copilot.config") or _mock_config
    sys.modules["src.copilot.graph"] = sys.modules.get("src.copilot.graph") or MagicMock()
    sys.modules["src.copilot.tools"] = sys.modules.get("src.copilot.tools") or MagicMock(available_tools=[])

from src.api.services.golden_example_service import (
    GoldenExampleService,
    build_prompt_with_golden_examples,
    search_golden_examples_sync,
    ensure_collection_exists,
    _get_embeddings,
    _get_qdrant_client,
)
from src.api.services.golden_response_generator import (
    GoldenResponseGenerator,
    GenerationResult,
    get_golden_response_generator,
)

if _needs_cleanup:
    for k in _copilot_mods:
        if _orig[k] is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = _orig[k]

async def _create_user(session, email=None):
    uid = uuid4()
    user = User(id=uid, email=email or f"u-{str(uid)[:8]}@test.com", is_active=True)
    session.add(user)
    await session.flush()
    return user


async def _create_golden_example(session, **overrides):
    defaults = dict(
        original_query="How do I reset my password?",
        original_response="Click forgot password.",
        golden_response="Go to Settings > Security > Reset Password.",
        source_type="manual",
        approval_type="manual",
        is_active=True,
    )
    defaults.update(overrides)
    ge = GoldenExample(**defaults)
    session.add(ge)
    await session.flush()
    return ge

class TestGoldenExampleServiceGetById:
    @pytest.mark.asyncio
    async def test_found(self, test_session):
        ge = await _create_golden_example(test_session)
        await test_session.commit()
        await test_session.refresh(ge)

        svc = GoldenExampleService(test_session)
        found = await svc.get_by_id(ge.id)
        assert found is not None
        assert found.id == ge.id

    @pytest.mark.asyncio
    async def test_not_found(self, test_session):
        svc = GoldenExampleService(test_session)
        found = await svc.get_by_id(uuid4())
        assert found is None


class TestGoldenExampleServiceList:
    @pytest.mark.asyncio
    async def test_list_empty(self, test_session):
        svc = GoldenExampleService(test_session)
        items, total = await svc.list_examples()
        assert items == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_returns_items(self, test_session):
        await _create_golden_example(test_session)
        await test_session.commit()

        svc = GoldenExampleService(test_session)
        items, total = await svc.list_examples()
        assert total == 1
        assert len(items) == 1
        assert items[0]["original_query"] == "How do I reset my password?"

    @pytest.mark.asyncio
    async def test_list_with_source_type_filter(self, test_session):
        await _create_golden_example(test_session, source_type="positive")
        await _create_golden_example(test_session, source_type="negative", original_query="Q2")
        await test_session.commit()

        svc = GoldenExampleService(test_session)
        items, total = await svc.list_examples(source_type_filter="positive")
        assert total == 1
        assert items[0]["source_type"] == "positive"

    @pytest.mark.asyncio
    async def test_list_with_active_filter(self, test_session):
        await _create_golden_example(test_session, is_active=True)
        await _create_golden_example(test_session, is_active=False, original_query="Q2")
        await test_session.commit()

        svc = GoldenExampleService(test_session)
        items, total = await svc.list_examples(is_active_filter=True)
        assert total == 1
        assert items[0]["is_active"] is True

    @pytest.mark.asyncio
    async def test_list_with_search(self, test_session):
        await _create_golden_example(test_session, original_query="How to fix login error?")
        await _create_golden_example(test_session, original_query="Something else", golden_response="unrelated")
        await test_session.commit()

        svc = GoldenExampleService(test_session)
        items, total = await svc.list_examples(search="login")
        assert total == 1

    @pytest.mark.asyncio
    async def test_list_pagination(self, test_session):
        for i in range(5):
            await _create_golden_example(test_session, original_query=f"Q{i}")
        await test_session.commit()

        svc = GoldenExampleService(test_session)
        items, total = await svc.list_examples(limit=2, offset=0)
        assert total == 5
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_list_with_creator(self, test_session):
        user = await _create_user(test_session)
        await _create_golden_example(test_session, created_by=user.id)
        await test_session.commit()

        svc = GoldenExampleService(test_session)
        items, total = await svc.list_examples()
        assert total == 1
        assert items[0]["creator_email"] == user.email


class TestGoldenExampleServiceCreate:
    @pytest.mark.asyncio
    async def test_create_with_embed_success(self, test_session):
        svc = GoldenExampleService(test_session)

        with patch.object(svc, "_embed_example", new_callable=AsyncMock, return_value="point-123"):
            ge = await svc.create_example(
                original_query="Q?",
                golden_response="A!",
                original_response="Old A",
            )
        assert ge.original_query == "Q?"
        assert ge.golden_response == "A!"
        assert ge.qdrant_point_id == "point-123"

    @pytest.mark.asyncio
    async def test_create_with_embed_failure(self, test_session):
        svc = GoldenExampleService(test_session)

        with patch.object(svc, "_embed_example", new_callable=AsyncMock, side_effect=RuntimeError("qdrant down")):
            ge = await svc.create_example(
                original_query="Q?",
                golden_response="A!",
            )
        assert ge.original_query == "Q?"
        assert ge.qdrant_point_id is None

    @pytest.mark.asyncio
    async def test_create_with_metadata(self, test_session):
        user = await _create_user(test_session)
        svc = GoldenExampleService(test_session)

        with patch.object(svc, "_embed_example", new_callable=AsyncMock, return_value="pt"):
            ge = await svc.create_example(
                original_query="Q?",
                golden_response="A!",
                created_by=user.id,
                source_type="positive",
                approval_type="auto",
                feedback_id=uuid4(),
            )
        assert ge.source_type == "positive"
        assert ge.approval_type == "auto"
        assert ge.created_by == user.id


class TestGoldenExampleServiceUpdate:
    @pytest.mark.asyncio
    async def test_update_response_reembeds(self, test_session):
        ge = await _create_golden_example(test_session, qdrant_point_id="old-point")
        await test_session.commit()
        await test_session.refresh(ge)

        svc = GoldenExampleService(test_session)
        with patch.object(svc, "_embed_example", new_callable=AsyncMock, return_value="new-point"), \
             patch.object(svc, "_delete_from_qdrant", new_callable=AsyncMock):
            result = await svc.update_example(ge.id, golden_response="Better answer")
        assert result.golden_response == "Better answer"
        assert result.qdrant_point_id == "new-point"

    @pytest.mark.asyncio
    async def test_update_is_active(self, test_session):
        ge = await _create_golden_example(test_session, is_active=True)
        await test_session.commit()
        await test_session.refresh(ge)

        svc = GoldenExampleService(test_session)
        result = await svc.update_example(ge.id, is_active=False)
        assert result.is_active is False

    @pytest.mark.asyncio
    async def test_update_not_found(self, test_session):
        svc = GoldenExampleService(test_session)
        result = await svc.update_example(uuid4(), golden_response="X")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_embed_failure_keeps_record(self, test_session):
        ge = await _create_golden_example(test_session, qdrant_point_id="old")
        await test_session.commit()
        await test_session.refresh(ge)

        svc = GoldenExampleService(test_session)
        with patch.object(svc, "_embed_example", new_callable=AsyncMock, side_effect=RuntimeError("fail")), \
             patch.object(svc, "_delete_from_qdrant", new_callable=AsyncMock):
            result = await svc.update_example(ge.id, golden_response="New")
        assert result.golden_response == "New"

    @pytest.mark.asyncio
    async def test_update_same_response_no_reembed(self, test_session):
        ge = await _create_golden_example(test_session, golden_response="Same")
        await test_session.commit()
        await test_session.refresh(ge)

        svc = GoldenExampleService(test_session)
        with patch.object(svc, "_embed_example", new_callable=AsyncMock) as mock_embed:
            result = await svc.update_example(ge.id, golden_response="Same")
        mock_embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_response_no_old_qdrant_point(self, test_session):
        ge = await _create_golden_example(test_session, qdrant_point_id=None)
        await test_session.commit()
        await test_session.refresh(ge)

        svc = GoldenExampleService(test_session)
        with patch.object(svc, "_embed_example", new_callable=AsyncMock, return_value="new-pt") as mock_embed, \
             patch.object(svc, "_delete_from_qdrant", new_callable=AsyncMock) as mock_del:
            result = await svc.update_example(ge.id, golden_response="Different")
        mock_del.assert_not_called()
        mock_embed.assert_called_once()


class TestGoldenExampleServiceDelete:
    @pytest.mark.asyncio
    async def test_delete_with_qdrant_point(self, test_session):
        ge = await _create_golden_example(test_session, qdrant_point_id="pt-del")
        await test_session.commit()
        await test_session.refresh(ge)
        gid = ge.id

        svc = GoldenExampleService(test_session)
        with patch.object(svc, "_delete_from_qdrant", new_callable=AsyncMock):
            result = await svc.delete_example(gid)
        assert result is True
        assert await svc.get_by_id(gid) is None

    @pytest.mark.asyncio
    async def test_delete_without_qdrant_point(self, test_session):
        ge = await _create_golden_example(test_session, qdrant_point_id=None)
        await test_session.commit()
        await test_session.refresh(ge)

        svc = GoldenExampleService(test_session)
        result = await svc.delete_example(ge.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_not_found(self, test_session):
        svc = GoldenExampleService(test_session)
        result = await svc.delete_example(uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_qdrant_failure_still_deletes(self, test_session):
        ge = await _create_golden_example(test_session, qdrant_point_id="pt-fail")
        await test_session.commit()
        await test_session.refresh(ge)

        svc = GoldenExampleService(test_session)
        with patch.object(svc, "_delete_from_qdrant", new_callable=AsyncMock, side_effect=RuntimeError("qdrant")):
            result = await svc.delete_example(ge.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_deactivate(self, test_session):
        ge = await _create_golden_example(test_session, is_active=True)
        await test_session.commit()
        await test_session.refresh(ge)

        svc = GoldenExampleService(test_session)
        result = await svc.deactivate_example(ge.id)
        assert result.is_active is False


class TestGoldenExampleServiceEmbed:
    @pytest.mark.asyncio
    async def test_embed_example(self, test_session):
        ge = await _create_golden_example(test_session)
        await test_session.commit()
        await test_session.refresh(ge)

        svc = GoldenExampleService(test_session)
        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1] * 384
        mock_client = MagicMock()
        mock_collections = MagicMock()
        _col = MagicMock(); _col.name = "golden_examples"
        mock_collections.collections = [_col]
        mock_client.get_collections.return_value = mock_collections

        with patch("src.api.services.golden_example_service._get_embeddings", return_value=mock_embeddings), \
             patch("src.api.services.golden_example_service._get_qdrant_client", return_value=mock_client):
            point_id = await svc._embed_example(ge)
        assert point_id == str(ge.id)
        mock_client.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_from_qdrant(self, test_session):
        svc = GoldenExampleService(test_session)
        mock_client = MagicMock()

        with patch("src.api.services.golden_example_service._get_qdrant_client", return_value=mock_client):
            await svc._delete_from_qdrant("point-123")
        mock_client.delete.assert_called_once()


class TestSearchSimilarExamples:
    @pytest.mark.asyncio
    async def test_search_success(self, test_session):
        svc = GoldenExampleService(test_session)
        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1] * 384
        mock_client = MagicMock()
        mock_collections = MagicMock()
        _col = MagicMock(); _col.name = "golden_examples"
        mock_collections.collections = [_col]
        mock_client.get_collections.return_value = mock_collections

        mock_result = MagicMock()
        mock_result.id = "pt-1"
        mock_result.score = 0.9
        mock_result.payload = {
            "original_query": "How to reset?",
            "golden_response": "Go to settings.",
            "source_type": "manual",
        }
        mock_client.search.return_value = [mock_result]

        with patch("src.api.services.golden_example_service._get_embeddings", return_value=mock_embeddings), \
             patch("src.api.services.golden_example_service._get_qdrant_client", return_value=mock_client):
            results = await svc.search_similar_examples("How to reset password?")
        assert len(results) == 1
        assert results[0]["score"] == 0.9

    @pytest.mark.asyncio
    async def test_search_exception_returns_empty(self, test_session):
        svc = GoldenExampleService(test_session)
        with patch("src.api.services.golden_example_service._get_qdrant_client", side_effect=RuntimeError("fail")):
            results = await svc.search_similar_examples("query")
        assert results == []


class TestSearchGoldenExamplesSync:
    def test_success(self):
        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1] * 384
        mock_client = MagicMock()
        mock_collections = MagicMock()
        _col = MagicMock(); _col.name = "golden_examples"
        mock_collections.collections = [_col]
        mock_client.get_collections.return_value = mock_collections

        mock_result = MagicMock()
        mock_result.id = "pt-sync"
        mock_result.score = 0.8
        mock_result.payload = {"original_query": "Q", "golden_response": "A", "source_type": "manual"}
        mock_client.search.return_value = [mock_result]

        with patch("src.api.services.golden_example_service._get_embeddings", return_value=mock_embeddings), \
             patch("src.api.services.golden_example_service._get_qdrant_client", return_value=mock_client):
            results = search_golden_examples_sync("query")
        assert len(results) == 1

    def test_exception_returns_empty(self):
        with patch("src.api.services.golden_example_service._get_qdrant_client", side_effect=RuntimeError("fail")):
            results = search_golden_examples_sync("query")
        assert results == []


class TestEnsureCollectionExists:
    def test_creates_collection_if_missing(self):
        mock_client = MagicMock()
        mock_collections = MagicMock()
        mock_collections.collections = []
        mock_client.get_collections.return_value = mock_collections

        with patch("src.api.services.golden_example_service._get_qdrant_client", return_value=mock_client):
            ensure_collection_exists()
        mock_client.create_collection.assert_called_once()

    def test_skips_if_exists(self):
        mock_client = MagicMock()
        mock_collections = MagicMock()
        existing_col = MagicMock()
        existing_col.name = "golden_examples"
        mock_collections.collections = [existing_col]
        mock_client.get_collections.return_value = mock_collections

        with patch("src.api.services.golden_example_service._get_qdrant_client", return_value=mock_client):
            ensure_collection_exists()
        mock_client.create_collection.assert_not_called()


class TestGetQdrantClient:
    def test_without_api_key(self):
        import src.api.services.golden_example_service as ges
        old_client = ges._qdrant_client
        ges._qdrant_client = None
        try:
            with patch.object(ges.config, "QDRANT_URL", "http://localhost:6333"), \
                 patch.object(ges.config, "QDRANT_API_KEY", ""), \
                 patch("src.api.services.golden_example_service.QdrantClient") as mock_cls:
                _get_qdrant_client()
            mock_cls.assert_called_once_with(url="http://localhost:6333")
        finally:
            ges._qdrant_client = old_client

    def test_with_api_key(self):
        import src.api.services.golden_example_service as ges
        old_client = ges._qdrant_client
        ges._qdrant_client = None
        try:
            with patch.object(ges.config, "QDRANT_URL", "http://localhost:6333"), \
                 patch.object(ges.config, "QDRANT_API_KEY", "secret"), \
                 patch("src.api.services.golden_example_service.QdrantClient") as mock_cls:
                _get_qdrant_client()
            mock_cls.assert_called_once_with(url="http://localhost:6333", api_key="secret")
        finally:
            ges._qdrant_client = old_client

    def test_no_url_raises(self):
        import src.api.services.golden_example_service as ges
        old_client = ges._qdrant_client
        ges._qdrant_client = None
        try:
            with patch.object(ges.config, "QDRANT_URL", ""), \
                 pytest.raises(ValueError, match="QDRANT_URL"):
                _get_qdrant_client()
        finally:
            ges._qdrant_client = old_client


class TestGetEmbeddings:
    def test_lazy_init(self):
        import src.api.services.golden_example_service as ges
        old_emb = ges._embeddings
        ges._embeddings = None
        try:
            with patch("src.api.services.golden_example_service.HuggingFaceEmbeddings") as mock_cls:
                mock_cls.return_value = MagicMock()
                result = _get_embeddings()
            mock_cls.assert_called_once()
            assert result is not None
        finally:
            ges._embeddings = old_emb

class TestBuildPromptWithGoldenExamples:
    def test_empty_examples(self):
        result = build_prompt_with_golden_examples("base prompt", [])
        assert result == "base prompt"

    def test_low_confidence_examples(self):
        examples = [
            {"score": 0.6, "original_query": "Q1", "golden_response": "A1"},
        ]
        result = build_prompt_with_golden_examples("base", examples)
        assert "base" in result
        assert "Reference" in result
        assert "Q1" in result
        assert "A1" in result

    def test_high_confidence_example(self):
        examples = [
            {"score": 0.95, "original_query": "Q1", "golden_response": "A1"},
        ]
        result = build_prompt_with_golden_examples("base", examples)
        assert "Direct Answer Available" in result
        assert "HIGH CONFIDENCE" in result

    def test_mixed_confidence(self):
        examples = [
            {"score": 0.95, "original_query": "Q1", "golden_response": "A1"},
            {"score": 0.6, "original_query": "Q2", "golden_response": "A2"},
        ]
        result = build_prompt_with_golden_examples("base", examples)
        assert "HIGH CONFIDENCE" in result
        assert "Reference" in result

    def test_custom_threshold(self):
        examples = [
            {"score": 0.7, "original_query": "Q1", "golden_response": "A1"},
        ]
        result = build_prompt_with_golden_examples("base", examples, direct_answer_threshold=0.6)
        assert "HIGH CONFIDENCE" in result

class TestGoldenResponseGenerator:
    @pytest.mark.asyncio
    async def test_generate_success(self):
        gen = GoldenResponseGenerator()
        mock_result = GenerationResult(
            generated_response="Better answer",
            tool_calls_made=0,
            generation_time_ms=100,
            success=True,
        )
        with patch.object(gen, "_generate_internal", new_callable=AsyncMock, return_value=mock_result):
            result = await gen.generate("Q?", "Bad A", "It was wrong", "negative")
        assert result.success is True
        assert result.generated_response == "Better answer"

    @pytest.mark.asyncio
    async def test_generate_timeout(self):
        gen = GoldenResponseGenerator()
        gen.GENERATION_TIMEOUT = 0.001

        async def slow_gen(**kwargs):
            await asyncio.sleep(10)
            return GenerationResult("", 0, 0, True)

        with patch.object(gen, "_generate_internal", side_effect=slow_gen):
            result = await gen.generate("Q?", "A", None, "negative")
        assert result.success is False
        assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_generate_exception(self):
        gen = GoldenResponseGenerator()

        with patch.object(gen, "_generate_internal", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
            result = await gen.generate("Q?", "A", None, "negative")
        assert result.success is False
        assert "boom" in result.error

    @pytest.mark.asyncio
    async def test_generate_internal_positive(self):
        gen = GoldenResponseGenerator()
        mock_response = MagicMock()
        mock_response.content = "Improved response"
        mock_response.tool_calls = []

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch.object(gen, "_get_llm", return_value=mock_llm), \
             patch.object(gen, "_get_tools", return_value=[]):
            result = await gen._generate_internal("Q?", "A", None, "positive")
        assert result.success is True
        assert result.generated_response == "Improved response"

    @pytest.mark.asyncio
    async def test_generate_internal_with_feedback_reason(self):
        gen = GoldenResponseGenerator()
        mock_response = MagicMock()
        mock_response.content = "Fixed"
        mock_response.tool_calls = []

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch.object(gen, "_get_llm", return_value=mock_llm), \
             patch.object(gen, "_get_tools", return_value=[]):
            result = await gen._generate_internal("Q?", "A", "wrong info", "negative")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_generate_internal_with_tools(self):
        gen = GoldenResponseGenerator()

        tool_response = MagicMock()
        tool_response.content = ""
        tool_response.tool_calls = [{"name": "search", "args": {"q": "test"}, "id": "tc1"}]

        final_response = MagicMock()
        final_response.content = "Final answer"
        final_response.tool_calls = []

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(side_effect=[tool_response, final_response])

        mock_tool = MagicMock()
        mock_tool.name = "search"
        mock_tool.invoke.return_value = "tool result"

        with patch.object(gen, "_get_llm", return_value=mock_llm), \
             patch.object(gen, "_get_tools", return_value=[mock_tool]):
            result = await gen._generate_internal("Q?", "A", "Feedback", "negative")
        assert result.success is True
        assert result.tool_calls_made == 1

    @pytest.mark.asyncio
    async def test_execute_single_tool_success(self):
        gen = GoldenResponseGenerator()
        mock_tool = MagicMock()
        mock_tool.name = "search_similar_incidents"
        mock_tool.invoke.return_value = "found incident INC-123"

        with patch.object(gen, "_get_tools", return_value=[mock_tool]):
            result = await gen._execute_single_tool({
                "name": "search_similar_incidents",
                "args": {"query": "test"},
                "id": "tc1",
            })
        assert "found incident INC-123" in result.content

    @pytest.mark.asyncio
    async def test_execute_single_tool_not_found(self):
        gen = GoldenResponseGenerator()
        with patch.object(gen, "_get_tools", return_value=[]):
            result = await gen._execute_single_tool({
                "name": "nonexistent_tool",
                "args": {},
                "id": "tc2",
            })
        assert "Unknown tool" in result.content

    @pytest.mark.asyncio
    async def test_execute_single_tool_error(self):
        gen = GoldenResponseGenerator()
        mock_tool = MagicMock()
        mock_tool.name = "bad_tool"
        mock_tool.invoke.side_effect = RuntimeError("tool crash")

        with patch.object(gen, "_get_tools", return_value=[mock_tool]):
            result = await gen._execute_single_tool({
                "name": "bad_tool",
                "args": {},
                "id": "tc3",
            })
        assert "Error executing tool" in result.content

    @pytest.mark.asyncio
    async def test_get_llm_lazy_init(self):
        """_get_llm lazily imports and caches LLM instance (lines 111-114)."""
        gen = GoldenResponseGenerator()
        mock_llm = MagicMock()
        with patch("src.copilot.graph.get_configured_llm", return_value=mock_llm):
            result = gen._get_llm()
        assert result is mock_llm
        # Second call returns cached
        assert gen._get_llm() is mock_llm

    @pytest.mark.asyncio
    async def test_get_tools_lazy_init(self):
        """_get_tools lazily imports and caches tools list (lines 118-121)."""
        gen = GoldenResponseGenerator()
        mock_tools = [MagicMock(), MagicMock()]
        with patch.dict("sys.modules", {"src.copilot.tools": MagicMock(available_tools=mock_tools)}):
            result = gen._get_tools()
        assert result is mock_tools
        # Second call returns cached
        assert gen._get_tools() is mock_tools

    @pytest.mark.asyncio
    async def test_max_iterations_forces_final(self):
        gen = GoldenResponseGenerator()
        gen.MAX_TOOL_ITERATIONS = 1

        tool_response = MagicMock()
        tool_response.content = ""
        tool_response.tool_calls = [{"name": "search", "args": {}, "id": "tc"}]

        final_response = MagicMock()
        final_response.content = "Final"
        final_response.tool_calls = []

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(side_effect=[tool_response, final_response])

        mock_tool = MagicMock()
        mock_tool.name = "search"
        mock_tool.invoke.return_value = "data"

        with patch.object(gen, "_get_llm", return_value=mock_llm), \
             patch.object(gen, "_get_tools", return_value=[mock_tool]):
            result = await gen._generate_internal("Q?", "A", None, "negative")
        assert result.generated_response == "Final"


class TestGetGoldenResponseGenerator:
    def test_singleton(self):
        import src.api.services.golden_response_generator as grg
        old = grg._generator_instance
        grg._generator_instance = None
        try:
            g1 = get_golden_response_generator()
            g2 = get_golden_response_generator()
            assert g1 is g2
        finally:
            grg._generator_instance = old

    def test_semaphore_lazy_init(self):
        GoldenResponseGenerator._semaphore = None
        sem = GoldenResponseGenerator._get_semaphore()
        assert sem is not None
        assert GoldenResponseGenerator._get_semaphore() is sem
        GoldenResponseGenerator._semaphore = None