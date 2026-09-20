import pytest
from src.finabstain.config import AppConfig
from src.finabstain.stages.s02_chunk import split_into_blocks, merge_blocks_into_sections, is_boilerplate

def test_split_and_merge_blocks():
    text = "Block 1 line 1.\nBlock 1 line 2.\n\nBlock 2 line 1.\n\nBlock 3 line 1."
    blocks = split_into_blocks(text)
    assert len(blocks) == 3

    # Merge blocks
    sections = merge_blocks_into_sections(blocks, min_words=2, max_words=100)
    assert len(sections) == 1

def test_boilerplate_detection():
    assert is_boilerplate("Item 1. Table of Contents\nPart I") is True
    assert is_boilerplate("SIGNATURES\nPursuant to the requirements of the Securities Exchange Act") is True
    assert is_boilerplate("Total net sales were $637,959 million in fiscal 2024.") is False
