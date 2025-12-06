import json
import re
from pathlib import Path
from typing import Tuple
from sentence_transformers import SentenceTransformer
import numpy as np

SEMANTIC_AVAILABLE = True


class PromptGuardrail:
    """Simple guardrail that rejects prompts containing absolute negative keywords.

    Behavior:
    - Treats single-word entries as token matches (word boundaries).
    - Only rejects when a denylist phrase or token is present (case-insensitive).

    This intentionally allows vague prompts and misspellings; only exact denylist
    entries trigger rejection.
    """

    def __init__(self, deny_words: str = None, denylist_path: str = None):
        self.deny_words = deny_words
        if denylist_path:
            self.denylist_path = Path(denylist_path)
        else:
            self.denylist_path = (
                Path(__file__).resolve().parents[2] / "data" / "denylist.json"
            )
        self.semantic_threshold = 0.7
        self.semantic_model_name = "all-MiniLM-L6-v2"
        self._semantic_model = None
        self._denylist_embeddings = None

        self._load_denylist()
        if SEMANTIC_AVAILABLE:
            try:
                self._init_semantic_model()
            except Exception:
                self._semantic_model = None

    def _load_denylist(self) -> None:
        raw = []
        
        try:
            with open(self.denylist_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, dict) and "denylist" in data:
                    raw = data.get("denylist", [])
                elif isinstance(data, list):
                    raw = data
        except Exception:
            pass

        if self.deny_words:
            settings_words = [
                word.strip() for word in self.deny_words.split(",") if word.strip()
            ]
            raw.extend(settings_words)

        entries = [str(x).strip().lower() for x in raw if x]
        self.phrases = [p for p in entries if " " in p]
        self.words = set(p for p in entries if " " not in p)

    def contains_denylist_keyword(self, text: str) -> bool:
        if not text:
            return False
        lowered = text.lower()
        
        for phrase in self.phrases:
            if phrase in lowered:
                return True

        tokens = re.findall(r"\w+", lowered)
        token_set = set(tokens)
        
        if any(word in token_set for word in self.words):
            return True

        return False

    def _matches_programming_regex(self, text: str) -> bool:
        """Fast heuristics to catch programming/code-generation prompts."""
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
        """Semantic check against denylist entries.
        Returns True when the prompt should be rejected.
        """
        if not SEMANTIC_AVAILABLE:
            return False
        try:
            if self._semantic_model is None:
                self._init_semantic_model()
            if self._semantic_model is None:
                return False
            emb = self._semantic_model.encode([text], convert_to_numpy=True)
            norm = np.linalg.norm(emb, axis=1, keepdims=True)
            norm[norm == 0] = 1.0
            emb = emb / norm
            if getattr(self, "_denylist_embeddings", None) is not None:
                try:
                    sims = np.dot(self._denylist_embeddings, emb.T).squeeze()
                    max_sim = float(np.max(sims)) if sims.size else 0.0
                    if max_sim >= self.semantic_threshold:
                        return True
                except Exception:
                    pass

        except Exception:
            return False
        return False

    def validate_or_reject(
        self, prompt: str, isContext: bool = False
    ) -> Tuple[bool, str]:
        """Return (True, "") when allowed, or (False, message) when rejected."""
        try:
            if self._matches_programming_regex(prompt):
                msg = "I cannot help with programming, may be I can help you with an query regarding incidents"
                return False, msg
        except Exception:
            pass

        if self.contains_denylist_keyword(prompt):
            msg = "I cannot help with that, may be I can help you with an query regarding incidents"
            return False, msg

        if isContext:
            return True, ""

        try:
            if self._semantic_check(prompt):
                msg = "I cannot help with that, may be I can help you with an query regarding incidents"
                return False, msg
        except Exception:
            pass

        return True, ""