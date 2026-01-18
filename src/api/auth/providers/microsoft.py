import logging
import urllib.parse
from typing import Dict, Any

import httpx
from fastapi import HTTPException, status

from .base import BaseProvider

logger = logging.getLogger(__name__)

# HTTP request timeout in seconds
HTTP_TIMEOUT = 30.0


class MicrosoftProvider(BaseProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client_id = config["client_id"]
        self.client_secret = config["client_secret"]
        self.redirect_uri = config["redirect_uri"]
        # Using 'common' for multi-tenant apps. Can be replaced with tenant ID if needed.
        self.tenant = config.get("tenant", "common")
        self.auth_endpoint = f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/authorize"
        self.token_endpoint = f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/token"
        self.graph_endpoint = "https://graph.microsoft.com/v1.0/me"

    async def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile User.Read",
            "state": state,
            "response_mode": "query"
        }
        return f"{self.auth_endpoint}?{urllib.parse.urlencode(params)}"

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            data = {
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
                "scope": "openid email profile User.Read"
            }

            resp = await client.post(self.token_endpoint, data=data)
            resp.raise_for_status()
            return resp.json()

    async def fetch_user_profile(self, token: Dict[str, Any]) -> Dict[str, Any]:
        access_token = token["access_token"]

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(
                self.graph_endpoint,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            resp.raise_for_status()
            user_info = resp.json()

        # Microsoft Graph API returns 'mail' or 'userPrincipalName'
        email = user_info.get("mail") or user_info.get("userPrincipalName")

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Microsoft account email not found"
            )

        return {
            "provider": "microsoft",
            "provider_user_id": user_info["id"],
            "email": email,
            "name": user_info.get("displayName"),
            # Microsoft Graph doesn't return avatar in /me by default, requires another call to /me/photo/$value
            # For now we can leave avatar empty or implement it later if needed.
            "avatar": None
        }
