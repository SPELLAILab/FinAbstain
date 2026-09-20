import random
from src.finabstain.stages.s08_build import construct_padded_context
from src.finabstain.textnorm import answer_in_text

def test_construct_padded_context():
    item_text = "This is the target item section with financial facts."
    fillers = [
        {"text": f"Filler section number {i} talking about unrelated business operations."}
        for i in range(10)
    ]
    rng = random.Random(42)
    context, target_pos, target_idx, tokens = construct_padded_context(
        item_text=item_text,
        fillers=fillers,
        target_tokens=200,
        rng=rng
    )

    assert "[Section" in context
    assert item_text in context
    assert 0.0 <= target_pos <= 1.0
    assert tokens > 0

def test_leakage_guard_detection():
    ans = "$637,959"
    safe_filler = "Filler section with revenues of $100,000 million."
    leaky_filler = "In this section, revenues of $637,959 were reported."

    assert answer_in_text(ans, leaky_filler) is True
    assert answer_in_text(ans, safe_filler) is False
