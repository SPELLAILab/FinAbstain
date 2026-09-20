from __future__ import annotations
import re
from pathlib import Path
from typing import List, Dict, Any

from ..config import AppConfig
from ..io_utils import write_jsonl_atomic
from ..textnorm import numbers_in

BOILERPLATE_PATTERNS = [
    r"(?:^|\n)\s*(?:item\s+\w+\.?\s*)?table of contents",
    r"exhibit index",
    r"exhibits? list",
    r"signatures?\s+pursuant to the requirements",
    r"power of attorney",
    r"consent of independent registered public accounting firm",
    r"certifications?\s+pursuant to\s+rule",
    r"principal executive officer certifications?",
    r"principal financial officer certifications?",
]

def is_boilerplate(text: str) -> bool:
    lower = text.lower()
    for pat in BOILERPLATE_PATTERNS:
        if re.search(pat, lower, flags=re.MULTILINE):
            return True
    return False

def split_into_blocks(text: str) -> List[str]:
    """Splits text into cohesive blocks (paragraphs and tables)."""
    raw_blocks = [b.strip() for b in re.split(r'\n{2,}', text) if b.strip()]
    refined_blocks = []
    for b in raw_blocks:
        words = b.split()
        if len(words) > 500:
            # Sub-split very large text blocks into ~250-word chunks on sentence boundaries
            sentences = re.split(r'(?<=[.!?])\s+', b)
            curr_s = []
            curr_w = 0
            for s in sentences:
                sw = len(s.split())
                if curr_w + sw > 350 and curr_w >= 150:
                    refined_blocks.append(" ".join(curr_s).strip())
                    curr_s = [s]
                    curr_w = sw
                else:
                    curr_s.append(s)
                    curr_w += sw
            if curr_s:
                refined_blocks.append(" ".join(curr_s).strip())
        else:
            refined_blocks.append(b)

    return refined_blocks

def merge_blocks_into_sections(blocks: List[str], min_words: int, max_words: int) -> List[str]:
    sections = []
    curr_blocks: List[str] = []
    curr_word_count = 0

    for block in blocks:
        block_words = len(block.split())

        # If adding this block exceeds max_words and we already meet min_words:
        if curr_word_count + block_words > max_words and curr_word_count >= min_words:
            sections.append("\n\n".join(curr_blocks).strip())
            curr_blocks = [block]
            curr_word_count = block_words
        else:
            curr_blocks.append(block)
            curr_word_count += block_words

    if curr_blocks:
        sections.append("\n\n".join(curr_blocks).strip())

    return sections

def run_stage(config: AppConfig, force: bool = False) -> Path:
    out_file = Path(config.data.out_dir) / "02_sections.jsonl"
    if not force and out_file.exists() and out_file.stat().st_size > 0:
        return out_file

    anon_dir = Path(config.data.out_dir) / "01_anonymized"
    anon_files = sorted(list(anon_dir.glob("*.txt")))

    records: List[Dict[str, Any]] = []
    sec_counter = 0

    for a_file in anon_files:
        report_id = a_file.stem
        text = a_file.read_text(encoding="utf-8")
        blocks = split_into_blocks(text)
        sections = merge_blocks_into_sections(
            blocks,
            min_words=config.sections.min_words,
            max_words=config.sections.max_words,
        )

        for s_idx, sec_text in enumerate(sections):
            n_words = len(sec_text.split())
            nums = numbers_in(sec_text)
            n_numbers = len(nums)
            bp = is_boilerplate(sec_text)

            eligible = (
                config.sections.min_words <= n_words <= (config.sections.max_words + 150)
                and n_numbers >= config.sections.min_numbers
                and not bp
            )

            rec = {
                "section_id": f"{report_id}_sec{sec_counter:04d}",
                "report_id": report_id,
                "index": sec_counter,
                "text": sec_text,
                "n_words": n_words,
                "n_numbers": n_numbers,
                "eligible": eligible,
            }
            records.append(rec)
            sec_counter += 1

    write_jsonl_atomic(out_file, records)
    return out_file
