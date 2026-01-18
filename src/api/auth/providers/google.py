import logging
import time
import urllib.parse
from typing import Dict, Any, Optional

import httpx
from fastapi import HTTPException, status

from .base import BaseProvider

logger = logging.getLogger(__name__)

# HTTP request timeout in seconds
HTTP_TIMEOUT = 30.0

# Discovery document cache (1 hour TTL)
_discovery_cache: Dict[str, Any] = {"doc": None, "expires": 0}
DISCOVERY_CACHE_TTL = 3600  # 1 hour


class GoogleProvider(BaseProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client_id = config["client_id"]
        self.client_secret = config["client_secret"]
        self.redirect_uri = config["redirect_uri"]
        self.discovery_url = "https://accounts.google.com/.well-known/openid-configuration"

    async def _get_discovery_document(self) -> Dict[str, Any]:
        """Fetch Google OIDC discovery document with caching."""
        global _discovery_cache

        if _discovery_cache["expires"] > time.time() and _discovery_cache["doc"]:
            return _discovery_cache["doc"]

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(self.discovery_url)
            resp.raise_for_status()
            discovery = resp.json()

        _discovery_cache["doc"] = discovery
        _discovery_cache["expires"] = time.time() + DISCOVERY_CACHE_TTL
        return discovery

    async def get_authorization_url(self, state: str) -> str:
        discovery = await self._get_discovery_document()
        auth_endpoint = discovery["authorization_endpoint"]

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline"
        }
        return f"{auth_endpoint}?{urllib.parse.urlencode(params)}"

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        discovery = await self._get_discovery_document()
        token_endpoint = discovery["token_endpoint"]

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            data = {
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code"
            }

            resp = await client.post(token_endpoint, data=data)
            resp.raise_for_status()
            return resp.json()

    async def fetch_user_profile(self, token: Dict[str, Any]) -> Dict[str, Any]:
        access_token = token["access_token"]
        discovery = await self._get_discovery_document()
        userinfo_endpoint = discovery["userinfo_endpoint"]

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(userinfo_endpoint, headers={"Authorization": f"Bearer {access_token}"})
            resp.raise_for_status()
            user_info = resp.json()

        if not user_info.get("email_verified"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google email not verified"
            )

        return {
            "provider": "google",
            "provider_user_id": user_info["sub"],
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "avatar": user_info.get("picture")
        }
