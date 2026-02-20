"""Tests for integrations credential masking utilities."""

import pytest
from unittest.mock import MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from src.api.routers.integrations import mask_sensitive_config, mask_integration_response


class TestCredentialMasking:
    """Tests for credential masking in integration responses."""

    def test_mask_sensitive_config_masks_password(self):
        """Test that password field is masked."""
        config = {
            "url": "https://example.com",
            "username": "admin",
            "password": "supersecret123"
        }
        masked = mask_sensitive_config(config)

        assert masked["url"] == "https://example.com"
        assert masked["username"] == "admin"
        assert masked["password"] == "********"

    def test_mask_sensitive_config_masks_api_key(self):
        """Test that api_key field is masked."""
        config = {
            "url": "https://api.example.com",
            "api_key": "sk-12345abcde"
        }
        masked = mask_sensitive_config(config)

        assert masked["url"] == "https://api.example.com"
        assert masked["api_key"] == "********"

    def test_mask_sensitive_config_masks_token(self):
        """Test that token fields are masked."""
        config = {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "refresh_token": "dGhpc2lzYXJlZnJlc2h0b2tlbg==",
            "token": "bearer-token-123"
        }
        masked = mask_sensitive_config(config)

        assert masked["access_token"] == "********"
        assert masked["refresh_token"] == "********"
        assert masked["token"] == "********"

    def test_mask_sensitive_config_masks_secret(self):
        """Test that secret fields are masked."""
        config = {
            "client_secret": "secret123",
            "api_secret": "apiSecret456"
        }
        masked = mask_sensitive_config(config)

        assert masked["client_secret"] == "********"
        assert masked["api_secret"] == "********"

    def test_mask_sensitive_config_preserves_non_sensitive(self):
        """Test that non-sensitive fields are preserved."""
        config = {
            "url": "https://example.com",
            "username": "admin",
            "port": 443,
            "enabled": True,
            "timeout": 30
        }
        masked = mask_sensitive_config(config)

        assert masked["url"] == "https://example.com"
        assert masked["username"] == "admin"
        assert masked["port"] == 443
        assert masked["enabled"] is True
        assert masked["timeout"] == 30

    def test_mask_sensitive_config_handles_empty(self):
        """Test that empty config is handled."""
        assert mask_sensitive_config({}) == {}
        assert mask_sensitive_config(None) is None

    def test_mask_sensitive_config_case_insensitive(self):
        """Test that field name matching is case-insensitive."""
        config = {
            "PASSWORD": "secret1",
            "Api_Key": "secret2",
            "TOKEN": "secret3"
        }
        masked = mask_sensitive_config(config)

        assert masked["PASSWORD"] == "********"
        assert masked["Api_Key"] == "********"
        assert masked["TOKEN"] == "********"

    def test_mask_integration_response(self):
        """Test that mask_integration_response creates properly masked response."""
        mock_integration = MagicMock()
        mock_integration.id = uuid4()
        mock_integration.service_name = "servicenow"
        mock_integration.auth_type = "basic_auth"
        mock_integration.config = {
            "url": "https://company.service-now.com",
            "username": "admin",
            "password": "supersecret"
        }
        mock_integration.is_active = True
        mock_integration.last_synced_at = datetime.now(timezone.utc)
        mock_integration.last_sync_status = "success"
        mock_integration.last_sync_error = None
        mock_integration.updated_at = datetime.now(timezone.utc)
        mock_integration.user_id = uuid4()

        masked = mask_integration_response(mock_integration)

        assert masked["service_name"] == "servicenow"
        assert masked["config"]["url"] == "https://company.service-now.com"
        assert masked["config"]["username"] == "admin"
        assert masked["config"]["password"] == "********"
        assert masked["is_active"] is True
