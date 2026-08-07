import re
from dataclasses import dataclass, field
from typing import List, Optional, Set
from better_profanity import profanity
from better_profanity.utils import read_wordlist


@dataclass
class GuardrailResult:
    is_safe: bool
    reason: Optional[str] = None
    censored_text: str = ""
    detected_words: List[str] = field(default_factory=list)


# Domain-specific whitelisted terms that should never be flagged as profanity
DEFAULT_DOMAIN_WHITELIST: Set[str] = {
    "pms",
    "pm-s",
    "ai-pms",
}


class GuardrailService:
    """
    Input Guardrail Service for detecting and blocking vulgar, filthy, and cuss words
    (including obfuscated / leetspeak variations) before processing RAG queries.
    """

    def __init__(
        self,
        custom_blocked_words: Optional[List[str]] = None,
        whitelist_words: Optional[Set[str]] = None
    ):
        # 1. Prepare wordlist excluding domain whitelisted words
        whitelisted = DEFAULT_DOMAIN_WHITELIST.union(whitelist_words or set())
        default_words = set(read_wordlist(profanity._default_wordlist_filename))
        clean_censor_words = list(default_words - whitelisted)

        # 2. Initialize profanity instance with clean censor list
        profanity.load_censor_words(custom_words=clean_censor_words)
        
        if custom_blocked_words:
            profanity.add_censor_words(custom_blocked_words)

        # 3. Regex patterns for additional obfuscated or aggressive vulgarity patterns
        self.vulgar_patterns = [
            re.compile(r'\b(f+[*a-z0-9]*[u4]+[*a-z0-9]*[c|k]+[*a-z0-9]*[k|t]*)\b', re.IGNORECASE),
            re.compile(r'\b(s+[*a-z0-9]*[h1|]+[*a-z0-9]*[i1|]+[*a-z0-9]*[t7]+)\b', re.IGNORECASE),
            re.compile(r'\b(b+[*a-z0-9]*[i1|]+[*a-z0-9]*[t7]+[*a-z0-9]*[c|k]+[*a-z0-9]*h*)\b', re.IGNORECASE),
            re.compile(r'\b(a+[*a-z0-9]*[s5\$]+[*a-z0-9]*[s5\$]+[*a-z0-9]*[h0|]+[*a-z0-9]*[o0]+[*a-z0-9]*l+[*a-z0-9]*e*)\b', re.IGNORECASE),
        ]

    def validate_input(self, text: str) -> GuardrailResult:
        """
        Validates user input text.
        Returns GuardrailResult with is_safe=True if input contains no inappropriate language,
        otherwise is_safe=False with explanation and censored version.
        """
        if not text or not text.strip():
            return GuardrailResult(is_safe=True, censored_text="")

        # 1. Check using better-profanity (catches standard profanity & obfuscation)
        contains_profanity = profanity.contains_profanity(text)

        # 2. Check using additional regex patterns
        pattern_matches = []
        for pattern in self.vulgar_patterns:
            matches = pattern.findall(text)
            if matches:
                pattern_matches.extend(matches)

        if contains_profanity or pattern_matches:
            censored = profanity.censor(text)
            return GuardrailResult(
                is_safe=False,
                reason="Input contains inappropriate, vulgar, or profanity language.",
                censored_text=censored,
                detected_words=list(set(pattern_matches))
            )

        return GuardrailResult(
            is_safe=True,
            reason=None,
            censored_text=text,
            detected_words=[]
        )
