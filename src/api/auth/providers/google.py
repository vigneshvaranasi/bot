from typing import Dict, Any
import httpx
import urllib.parse
from fastapi import HTTPException, status
from .base import BaseProvider

class GoogleProvider(BaseProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client_id = config["client_id"]
        self.client_secret = config["client_secret"]
        self.redirect_uri = config["redirect_uri"]
        self.discovery_url = "https://accounts.google.com/.well-known/openid-configuration"

    async def get_authorization_url(self, state: str) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.discovery_url)
            discovery = resp.json()
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
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.discovery_url)
            discovery = resp.json()
            token_endpoint = discovery["token_endpoint"]
            
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
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.discovery_url)
            discovery = resp.json()
            userinfo_endpoint = discovery["userinfo_endpoint"]
            
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
