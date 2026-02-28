"""Prompt guardrails for filtering inappropriate or out-of-scope queries.

This module provides security guardrails that validate user prompts
against denylists and semantic filters before processing.

Security Note: Guardrails fail CLOSED - if an error occurs during validation,
the prompt is rejected. This prevents potentially malicious prompts from
bypassing security checks due to errors.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Flag for semantic model availability
SEMANTIC_AVAILABLE = True

# Standard rejection message - extracted to avoid duplication
REJECTION_MESSAGE = "I cannot help with that, maybe I can help you with a query regarding incidents"
PROGRAMMING_REJECTION_MESSAGE = "I cannot help with programming, maybe I can help you with a query regarding incidents"

class PromptGuardrail:
    """Guardrail that rejects prompts containing denylist keywords or programming requests.

    Behavior:
    - Treats single-word entries as token matches (word boundaries).
    - Only rejects when a denylist phrase or token is present (case-insensitive).
    - Fails CLOSED on errors: rejects prompts if validation cannot complete.

    This intentionally allows vague prompts and misspellings; only exact denylist
    entries trigger rejection.
    """

    def __init__(
        self,
        deny_words: Optional[str] = None,
        denylist_path: Optional[str] = None
    ) -> None:
        """Initialize the guardrail with denylist configuration.

        Args:
            deny_words: Comma-separated string of words to deny
            denylist_path: Path to JSON file containing denylist
        """
        self.deny_words = deny_words
        if denylist_path:
            self.denylist_path = Path(denylist_path)
        else:
            self.denylist_path = (
                Path(__file__).resolve().parents[3] / "data" / "denylist.json"
            )
        self.semantic_threshold = 0.7
        self.semantic_model_name = "all-MiniLM-L6-v2"
        self._semantic_model: Optional[SentenceTransformer] = None
        self._denylist_embeddings: Optional[np.ndarray] = None
        self._entries: list = []

        self._load_denylist()
        if SEMANTIC_AVAILABLE:
            try:
                self._init_semantic_model()
            except Exception as e:
                logger.error(f"Failed to initialize semantic model: {e}")
                self._semantic_model = None

    def _load_denylist(self) -> None:
        """Load denylist from file and settings."""
        raw = []

        try:
            with open(self.denylist_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, dict) and "denylist" in data:
                    raw = data.get("denylist", [])
                elif isinstance(data, list):
                    raw = data
        except FileNotFoundError:
            logger.warning(f"Denylist file not found: {self.denylist_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in denylist file: {e}")
        except Exception as e:
            logger.error(f"Error loading denylist: {e}")

        if self.deny_words:
            settings_words = [
                word.strip() for word in self.deny_words.split(",") if word.strip()
            ]
            raw.extend(settings_words)

        entries = [str(x).strip().lower() for x in raw if x]
        self.phrases = [p for p in entries if " " in p]
        self.words = set(p for p in entries if " " not in p)

    def contains_denylist_keyword(self, text: str) -> bool:
        """Check if text contains any denylist keywords.

        Args:
            text: The text to check

        Returns:
            True if text contains denylist keywords, False otherwise
        """
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

    def _matches_programming_regex(self, text: str) -> bool:
        """Check if text matches programming/code-generation patterns.

        Args:
            text: The text to check

        Returns:
            True if text appears to be a programming request
        """
        if not text:
            return False
        lowered = text.lower()
        patterns = [
            r"\bwrite\s+(a|an|the)?\s*.*\b(program|script|application|example|code)\b",
            r"\b(example|sample|show|provide)\b.*\b(code|program|script)\b",
            r"\b(c\+\+|cpp|java|python|golang|go|rust|javascript|ts|typescript)\b",
            r"\bhow to implement\b",
            r"\b(read|open|write)\s+(a\s+)?file\b",
        ]
        for p in patterns:
            if re.search(p, lowered):
                return True
        return False

    def _init_semantic_model(self) -> None:
        """Load the sentence-transformers model and precompute denylist embeddings."""
        if not SEMANTIC_AVAILABLE:
            return
        if self._semantic_model is None:
            self._semantic_model = SentenceTransformer(self.semantic_model_name)

        self._entries = list(self.phrases) + list(self.words)
        if self._entries:
            embeds = self._semantic_model.encode(self._entries, convert_to_numpy=True)
            norms = np.linalg.norm(embeds, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self._denylist_embeddings = embeds / norms

    def _semantic_check(self, text: str) -> bool:
        """Perform semantic similarity check against denylist entries.

        Args:
            text: The text to check

        Returns:
            True if text is semantically similar to denylist entries (should reject)
        """
        if not SEMANTIC_AVAILABLE:
            return False

        try:
            if self._semantic_model is None:
                self._init_semantic_model()
            if self._semantic_model is None:
                # Model unavailable — skip semantic check; keyword check still guards.
                logger.warning("Semantic model unavailable, skipping semantic check")
                return False

            emb = self._semantic_model.encode([text], convert_to_numpy=True)
            norm = np.linalg.norm(emb, axis=1, keepdims=True)
            norm[norm == 0] = 1.0
            emb = emb / norm

            if getattr(self, "_denylist_embeddings", None) is not None:
                sims = np.dot(self._denylist_embeddings, emb.T).squeeze()
                max_sim = float(np.max(sims)) if sims.size else 0.0
                if max_sim >= self.semantic_threshold:
                    return True

        except Exception as e:
            # Fail closed: reject on error to prevent bypass
            logger.error(f"Semantic check failed, rejecting prompt: {e}")
            return True

        return False

    def validate_or_reject(
        self,
        prompt: str,
        is_context: bool = False
    ) -> Tuple[bool, str]:
        """Validate a prompt and return approval status.

        Args:
            prompt: The prompt text to validate
            is_context: If True, skip semantic check (for context validation)

        Returns:
            Tuple of (is_allowed, rejection_message).
            is_allowed is True with empty message if prompt is allowed.
            is_allowed is False with message if prompt should be rejected.
        """
        try:
            if self._matches_programming_regex(prompt):
                return False, PROGRAMMING_REJECTION_MESSAGE
        except Exception as e:
            # Fail closed: reject on error
            logger.error(f"Programming regex check failed, rejecting prompt: {e}")
            return False, REJECTION_MESSAGE

        if self.contains_denylist_keyword(prompt):
            return False, REJECTION_MESSAGE

        if is_context:
            return True, ""

        try:
            if self._semantic_check(prompt):
                return False, REJECTION_MESSAGE
        except Exception as e:
            # Fail closed: reject on error
            logger.error(f"Semantic check failed, rejecting prompt: {e}")
            return False, REJECTION_MESSAGE

        return True, ""
