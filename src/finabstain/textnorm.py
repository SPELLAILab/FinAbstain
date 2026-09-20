from __future__ import annotations
import re
import string
from typing import List, Set, Optional, Tuple

try:
    import tiktoken
    _TIKTOKEN_AVAILABLE = True
    _ENC = tiktoken.get_encoding("cl100k_base")
except Exception:
    _TIKTOKEN_AVAILABLE = False
    _ENC = None

RECONCILE_WORDS: Set[str] = {
    "restated", "revised", "revision", "corrected", "correction",
    "adjusted", "previously", "updated", "amended", "formerly",
    "initially", "originally", "supersede", "supersedes", "superseded"
}

def count_tokens(text: str) -> int:
    """Returns token count using tiktoken or approximation words * 1.3."""
    if not text:
        return 0
    if _TIKTOKEN_AVAILABLE and _ENC is not None:
        try:
            return len(_ENC.encode(text))
        except Exception:
            pass
    return int(len(text.split()) * 1.3)

def normalize_text(text: str) -> str:
    """Normalizes text by lowercasing, stripping punctuation, and collapsing whitespace."""
    if not text:
        return ""
    text = text.lower()
    # Replace common currency symbols and punctuation
    text = text.replace("$", "").replace("€", "").replace("£", "").replace("%", "")
    # Remove punctuation
    translator = str.maketrans("", "", string.punctuation)
    text = text.translate(translator)
    # Collapse whitespace
    return " ".join(text.split())

def parse_number_str(s: str) -> Optional[float]:
    """Parse a string representing a number (handling commas, parentheses for negative, etc.)."""
    s = s.strip()
    # Check parenthesized negative e.g. (1,234.50) or (50)
    is_neg = False
    if s.startswith("(") and s.endswith(")"):
        is_neg = True
        s = s[1:-1].strip()
    elif s.startswith("-"):
        is_neg = True
        s = s[1:].strip()

    # Remove currency symbols, commas, percent
    s = re.sub(r"[$€£,%]", "", s).strip()
    try:
        val = float(s)
        return -val if is_neg else val
    except ValueError:
        return None

def numbers_in(text: str) -> List[float]:
    """Extracts all numeric values from text, including negatives and formatted values."""
    if not text:
        return []
    # Match patterns like: $1,234.56, ($2,700), (1,234.56), -45.6, 123, 45%
    pattern = r'\(?\$?[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?\)?'
    matches = re.finditer(pattern, text)
    nums = []
    for m in matches:
        raw = m.group(0).strip()
        # Ensure it has at least one digit
        if not any(c.isdigit() for c in raw):
            continue
        val = parse_number_str(raw)
        if val is not None:
            nums.append(val)
    return nums

def relative_diff(val1: float, val2: float) -> float:
    """Computes relative difference between two numbers."""
    denom = max(abs(val1), abs(val2), 1e-7)
    return abs(val1 - val2) / denom

def has_reconcile_words(text: str) -> bool:
    """Checks if text contains any reconcile words."""
    norm = normalize_text(text)
    words = set(norm.split())
    return not words.isdisjoint(RECONCILE_WORDS)

def answer_in_text(answer: str, text: str) -> bool:
    """Returns True if the normalized answer or its numerical equivalent is present in text."""
    norm_ans = normalize_text(answer)
    norm_txt = normalize_text(text)
    if norm_ans and norm_ans in norm_txt:
        return True
    # Also check numeric match
    ans_nums = numbers_in(answer)
    if ans_nums:
        txt_nums = numbers_in(text)
        for an in ans_nums:
            for tn in txt_nums:
                if relative_diff(an, tn) < 1e-4:
                    return True
    return False
