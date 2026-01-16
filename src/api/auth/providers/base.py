from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseProvider(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    async def get_authorization_url(self, state: str) -> str:
        pass

    @abstractmethod
    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def fetch_user_profile(self, token: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return normalized profile:
        {
          "provider": "google",
          "provider_user_id": "123",
          "email": "user@gmail.com",
          "name": "User",
          "avatar": "url"
        }
        """
        pass
