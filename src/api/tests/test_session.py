"""Tests for database session handling."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock


class TestGetSession:
    """Tests for get_session dependency."""

    @pytest.mark.asyncio
    async def test_session_commits_on_success(self):
        """Test that session commits on successful operation."""
        # Create mock session
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_session_maker = MagicMock(return_value=mock_session)

        with patch("src.api.db.session.async_session", mock_session_maker):
            from src.api.db.session import get_session

            # Get the generator
            gen = get_session()
            session = await gen.__anext__()

            # Simulate successful operation
            try:
                await gen.__anext__()
            except StopAsyncIteration:
                pass

            # Verify commit was called
            mock_session.commit.assert_called_once()
            mock_session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_session_rolls_back_on_exception(self):
        """Test that session rolls back on exception."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_session_maker = MagicMock(return_value=mock_session)

        with patch("src.api.db.session.async_session", mock_session_maker):
            from src.api.db.session import get_session

            gen = get_session()
            session = await gen.__anext__()

            # Simulate exception
            with pytest.raises(ValueError):
                await gen.athrow(ValueError("Test error"))

            # Verify rollback was called
            mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_engine_not_disposed_on_exception(self):
        """Test that the global engine is NOT disposed on exception.

        This is the critical fix - the old code would dispose the engine
        on any exception, breaking all subsequent requests.
        """
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_session_maker = MagicMock(return_value=mock_session)
        mock_engine = AsyncMock()

        with patch("src.api.db.session.async_session", mock_session_maker):
            with patch("src.api.db.session.engine", mock_engine):
                from src.api.db.session import get_session

                gen = get_session()
                session = await gen.__anext__()

                # Simulate exception
                try:
                    await gen.athrow(ValueError("Test error"))
                except ValueError:
                    pass

                # Verify engine.dispose() was NOT called
                mock_engine.dispose.assert_not_called()
