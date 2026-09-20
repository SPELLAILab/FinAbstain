from __future__ import annotations
import re
import difflib
from typing import List, Tuple, Optional, Dict, Any
from .textnorm import normalize_text, answer_in_text

def clean_whitespace_after_deletion(text: str) -> str:
    """Cleans double spaces within lines and removes lines that became empty."""
    lines = []
    for line in text.splitlines():
        cleaned_line = re.sub(r"[ \t]{2,}", " ", line).strip()
        if cleaned_line:
            lines.append(cleaned_line)
    return "\n".join(lines).strip()

def apply_deletion(text: str, deletions: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Applies verbatim span deletions to text.
    Each span must appear exactly once in the current text.
    Returns (edited_text, error_message). If error, edited_text is None.
    """
    if not deletions:
        return None, "Deletions list is empty"

    current = text
    for span in deletions:
        if not span or not span.strip():
            continue
        count = current.count(span)
        if count == 0:
            return None, f"Deletion span not found: {span[:50]!r}"
        if count > 1:
            return None, f"Deletion span appears {count} times (must be exactly 1): {span[:50]!r}"
        current = current.replace(span, "")

    cleaned = clean_whitespace_after_deletion(current)
    return cleaned, None

def apply_insertion(text: str, anchor: str, inserted_text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Inserts `inserted_text` on a new line directly after the line containing `anchor`.
    `anchor` must appear exactly once in `text`.
    Returns (edited_text, error_message). If error, edited_text is None.
    """
    if not anchor or not anchor.strip():
        return None, "Anchor cannot be empty"
    if not inserted_text or not inserted_text.strip():
        return None, "Inserted text cannot be empty"

    count = text.count(anchor)
    if count == 0:
        return None, f"Anchor not found: {anchor[:50]!r}"
    if count > 1:
        return None, f"Anchor appears {count} times (must be exactly 1): {anchor[:50]!r}"

    lines = text.split("\n")
    # Find which line contains the anchor
    target_idx = -1
    for idx, line in enumerate(lines):
        if anchor in line:
            target_idx = idx
            break

    if target_idx == -1:
        # The anchor spans multiple lines; find the line where anchor ends
        pos = text.index(anchor) + len(anchor)
        lines_before = text[:pos].count("\n")
        target_idx = lines_before

    # Insert on a new line directly after target_idx
    new_lines = lines[:target_idx + 1] + [inserted_text.strip()] + lines[target_idx + 1:]
    result = "\n".join(new_lines).strip()
    return result, None

def verify_diff(original_text: str, edited_text: str, edit_type: str, edit_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Verifies using difflib that:
    - for insert: exactly one added block located right after the anchor line, and nothing else changed.
    - for delete: only removals at the given spans, and nothing else changed.
    """
    orig_lines = [l.strip() for l in original_text.splitlines() if l.strip()]
    edit_lines = [l.strip() for l in edited_text.splitlines() if l.strip()]

    matcher = difflib.SequenceMatcher(None, orig_lines, edit_lines)
    opcodes = matcher.get_opcodes()

    if edit_type in ("conflict", "ambiguous"):
        # Expecting equal blocks and exactly one insert block
        insert_count = 0
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == "insert":
                insert_count += 1
                inserted_content = " ".join(edit_lines[j1:j2]).strip()
                expected = " ".join(edit_data.get("inserted_text", "").split()).strip()
                if inserted_content != expected:
                    return False, f"Inserted diff does not match inserted_text: {inserted_content!r} vs {expected!r}"
            elif tag in ("delete", "replace"):
                return False, f"Unexpected change type '{tag}' in insertion edit"
        if insert_count != 1:
            return False, f"Expected exactly 1 insert block, found {insert_count}"
        return True, None

    elif edit_type == "missing":
        # Expecting equal blocks and delete blocks (or replace due to whitespace cleanup)
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == "insert":
                return False, "Unexpected insert block found in deletion edit"
        return True, None

    elif edit_type == "answerable":
        if original_text.strip() != edited_text.strip():
            return False, "Answerable item text was modified"
        return True, None

    return False, f"Unknown edit type: {edit_type}"

def deterministic_missing_fallback(
    text: str,
    answer: str,
    min_kept_ratio: float = 0.70
) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """
    Fallback for missing: splits into sentences/lines, deletes any sentence containing
    the answer, and ensures at least min_kept_ratio of words remain.
    """
    # Split text into lines or sentences
    lines = text.split("\n")
    new_lines = []
    deleted_spans = []

    for line in lines:
        if answer_in_text(answer, line):
            deleted_spans.append(line.strip())
        else:
            new_lines.append(line)

    if not deleted_spans:
        # Also try sentence splitting within lines
        return None, None, "Answer not detected in any specific line for deterministic fallback"

    candidate_text = clean_whitespace_after_deletion("\n".join(new_lines))
    orig_word_count = len(text.split())
    cand_word_count = len(candidate_text.split())

    if orig_word_count == 0:
        return None, None, "Empty original text"

    kept_ratio = cand_word_count / orig_word_count
    if kept_ratio < min_kept_ratio:
        return None, None, f"Fallback kept ratio {kept_ratio:.2f} < threshold {min_kept_ratio:.2f}"

    if answer_in_text(answer, candidate_text):
        return None, None, "Answer still present in text after fallback deletion"

    return candidate_text, {"deletions": deleted_spans, "fallback": True}, None
