from typing import Dict, Type, Optional
from .base import BaseProvider
from .google import GoogleProvider
from .github import GithubProvider
from .microsoft import MicrosoftProvider

PROVIDER_REGISTRY: Dict[str, Type[BaseProvider]] = {
    "google": GoogleProvider,
    "github": GithubProvider,
    "microsoft": MicrosoftProvider
}

def get_provider_class(name: str) -> Optional[Type[BaseProvider]]:
    return PROVIDER_REGISTRY.get(name)
