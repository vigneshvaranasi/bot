"""Prompt guardrails for filtering inappropriate or out-of-scope queries.

This module provides the L1 regex/denylist guardrail layer that runs before
any LLM call. Deeper semantic scope-checking is performed by the pluggable
LLM guardrail node in the agent graph (see `src/copilot/graph.py`).

Security Note: Guardrails fail CLOSED on errors — if regex validation cannot
complete, the prompt is rejected to prevent bypass.
"""

import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

REJECTION_MESSAGE = "I cannot help with that, maybe I can help you with a query regarding incidents"


class PromptGuardrail:
    """Regex/denylist guardrail that rejects prompts containing disallowed tokens.

    - Deny words come exclusively from the settings DB (comma-separated).
    - Treats single-word entries as token matches (word boundaries).
    - Multi-word phrases are matched as word-bounded substrings.
    - Case-insensitive.
    - Fails CLOSED on errors: rejects prompts if validation cannot complete.
    """

    def __init__(self, deny_words: Optional[str] = None) -> None:
        entries = []
        if deny_words:
            entries = [
                word.strip().lower()
                for word in deny_words.split(",")
                if word and word.strip()
            ]
        self.phrases = [p for p in entries if " " in p]
        self.words = set(p for p in entries if " " not in p)

    def contains_denylist_keyword(self, text: str) -> bool:
        if not text:
            return False
        lowered = text.lower()

        for phrase in self.phrases:
            if re.search(r"\b" + re.escape(phrase) + r"\b", lowered):
                return True

        tokens = re.findall(r"\w+", lowered)
        token_set = set(tokens)

        if any(word in token_set for word in self.words):
            return True

        return False

    def validate_or_reject(
        self,
        prompt: str,
        is_context: bool = False,
    ) -> Tuple[bool, str]:
        """Validate a prompt against the deny-words regex check.

        Args:
            prompt: The prompt text to validate.
            is_context: Retained for backwards compatibility; no longer used.

        Returns:
            Tuple of (is_allowed, rejection_message).
        """
        try:
            if self.contains_denylist_keyword(prompt):
                return False, REJECTION_MESSAGE
        except Exception as e:
            logger.error(f"Denylist check failed, rejecting prompt: {e}")
            return False, REJECTION_MESSAGE

        return True, ""
