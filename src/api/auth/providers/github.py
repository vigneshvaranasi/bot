import logging
import urllib.parse
from typing import Dict, Any

import httpx
from fastapi import HTTPException

from .base import BaseProvider

logger = logging.getLogger(__name__)

# HTTP request timeout in seconds
HTTP_TIMEOUT = 30.0


class GithubProvider(BaseProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client_id = config["client_id"]
        self.client_secret = config["client_secret"]
        self.redirect_uri = config["redirect_uri"]
        self.auth_url = "https://github.com/login/oauth/authorize"
        self.token_url = "https://github.com/login/oauth/access_token"
        self.user_url = "https://api.github.com/user"
        self.emails_url = "https://api.github.com/user/emails"

    async def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "user:email",
            "state": state
        }
        return f"{self.auth_url}?{urllib.parse.urlencode(params)}"

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": self.redirect_uri
            }
            headers = {"Accept": "application/json"}
            resp = await client.post(self.token_url, data=data, headers=headers)
            resp.raise_for_status()
            try:
                return resp.json()
            except Exception as e:
                logger.exception("Failed to parse GitHub token response")
                raise HTTPException(status_code=500, detail="Failed to parse authentication response")

    async def fetch_user_profile(self, token: Dict[str, Any]) -> Dict[str, Any]:
        access_token = token["access_token"]
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            # Fetch user info
            resp = await client.get(self.user_url, headers=headers)
            resp.raise_for_status()
            try:
                user_info = resp.json()
            except Exception as e:
                logger.exception("Failed to parse GitHub user response")
                raise HTTPException(status_code=500, detail="Failed to parse user profile")

            # Fetch emails if not public
            email = user_info.get("email")
            if not email:
                resp = await client.get(self.emails_url, headers=headers)
                resp.raise_for_status()
                try:
                    emails = resp.json()
                except Exception as e:
                    logger.exception("Failed to parse GitHub emails response")
                    raise HTTPException(status_code=500, detail="Failed to parse user emails")
                # Find primary verified email
                primary_email = next((e for e in emails if e["primary"] and e["verified"]), None)
                if primary_email:
                    email = primary_email["email"]

        # Validate email is present
        if not email:
            raise HTTPException(
                status_code=400,
                detail="GitHub account has no verified email. Please add a public email to your GitHub profile."
            )

        return {
            "provider": "github",
            "provider_user_id": str(user_info["id"]),
            "email": email,
            "name": user_info.get("name") or user_info.get("login"),
            "avatar": user_info.get("avatar_url")
        }
