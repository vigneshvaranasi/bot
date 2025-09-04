#!/usr/bin/env python3
import json
import re
from pathlib import Path
from typing import List, Set, Tuple


class PromptGuardrail:
    """Simple guardrail that rejects prompts containing absolute negative keywords.

    Behavior:
    - Loads `data/blacklist.json` from the repository root by default.
    - Treats single-word entries as token matches (word boundaries).
    - Only rejects when a blacklist phrase or token is present (case-insensitive).

    This intentionally allows vague prompts and misspellings; only exact blacklist
    entries trigger rejection.
    """

    def __init__(self, blacklist_path: str = None):
        if blacklist_path:
            self.blacklist_path = Path(blacklist_path)
        else:
            self.blacklist_path = Path(__file__).resolve().parents[2] / "data" / "blacklist.json"
        self._load_blacklist()

    def _load_blacklist(self) -> None:
        try:
            with open(self.blacklist_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            data = []

        if isinstance(data, dict) and "blacklist" in data:
            raw = data.get("blacklist", [])
        elif isinstance(data, list):
            raw = data
        else:
            raw = []

        entries = [str(x).strip().lower() for x in raw if x]
        # phrases (contain whitespace) vs single words
        self.phrases = [p for p in entries if " " in p]
        self.words = set(p for p in entries if " " not in p)

    def contains_blacklist_keyword(self, text: str) -> bool:
        if not text:
            return False
        lowered = text.lower()
        # check phrases first (substring)
        for phrase in self.phrases:
            if phrase in lowered:
                return True
        # tokenize by word characters
        tokens = re.findall(r"\w+", lowered)
        token_set = set(tokens)
        return any(w in token_set for w in self.words)

    def validate_or_reject(self, prompt: str) -> Tuple[bool, str]:
        """Return (True, "") when allowed, or (False, message) when rejected."""
        if self.contains_blacklist_keyword(prompt):
            msg = "I cannot help with that, may be I can help you with an query regarding incidents"
            return False, msg
        return True, ""
