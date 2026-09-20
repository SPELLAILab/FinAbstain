from __future__ import annotations
import os
import re
import json
import random
from pathlib import Path
from typing import Dict, Any, List, Tuple
from collections import Counter
import spacy

from ..config import AppConfig

# Common titles/roles in 10-Ks
ROLES = [
    "Chief Executive Officer", "CEO", "Chief Financial Officer", "CFO",
    "Chief Operating Officer", "COO", "Director", "President",
    "Vice President", "Secretary", "Treasurer", "Chairman"
]

def get_scale_factor(rng: random.Random, factor_range: List[float]) -> float:
    min_f, max_f = factor_range
    for _ in range(100):
        factor = rng.uniform(min_f, max_f)
        if not (0.9 <= factor <= 1.1):
            return round(factor, 4)
    return 1.35

def remove_pii(text: str) -> str:
    # URLs
    text = re.sub(r'https?://[^\s)\]]+', '[URL]', text)
    # Emails
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
    # Phone numbers e.g. (206) 266-1000 or 206-266-1000
    text = re.sub(r'\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b', '[PHONE]', text)
    # Common street addresses
    text = re.sub(r'\b\d{1,5}\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s+(?:Avenue|Street|Blvd|Boulevard|Road|Way|Drive|Lane|Pkwy|Parkway)\b', '[ADDRESS]', text)
    return text

def scale_number_match(match: re.Match, factor: float) -> str:
    full_str = match.group(0)
    prefix = match.group(1) or ""
    num_str = match.group(2)
    suffix = match.group(3) or ""

    # Don't scale if lookbehind indicated note/item
    has_parens = num_str.startswith("(") and num_str.endswith(")")
    clean_num = num_str.replace("(", "").replace(")", "").replace(",", "")

    try:
        val = float(clean_num)
    except ValueError:
        return full_str

    scaled_val = val * factor
    # Retain decimal places
    if "." in clean_num:
        decimals = len(clean_num.split(".")[1])
        fmt = f"{{:,.{decimals}f}}"
    else:
        fmt = "{:,.0f}"

    scaled_str = fmt.format(round(scaled_val, 2 if "." in clean_num else 0))
    if has_parens:
        scaled_str = f"({scaled_str})"
    return f"{prefix}{scaled_str}{suffix}"

def scale_amounts_and_shares(text: str, factor: float) -> str:
    # 1. Scale monetary amounts ($1,234.50 or $123)
    # Exclude percentages or ratios
    money_pattern = r'(\$)\s*(\(?\d{1,3}(?:,\d{3})*(?:\.\d+)?\)?)(\s*(?:million|billion|trillion)?)'
    text = re.sub(money_pattern, lambda m: scale_number_match(m, factor), text, flags=re.IGNORECASE)

    # 2. Scale share counts (e.g. 10,480,000,000 shares or 500 million shares)
    shares_pattern = r'(\b)(\(?\d{1,3}(?:,\d{3})*(?:\.\d+)?\)?)(\s*(?:million|billion)?\s+shares\b)'
    text = re.sub(shares_pattern, lambda m: scale_number_match(m, factor), text, flags=re.IGNORECASE)

    return text

GENERIC_WORDS = {
    "company", "corporation", "inc", "ltd", "llc", "corp", "address",
    "statements", "controls", "procedures", "cybersecurity", "corporate governance",
    "board", "directors", "management", "exhibit", "exhibits", "report", "filing",
    "mark one", "smaller", "legal proceedings", "financial statements",
    "supplementary data", "related transactions"
}

def anonymize_report(
    text: str,
    nlp: Any,
    config: AppConfig,
    report_id: str,
    seed: int
) -> Tuple[str, Dict[str, Any]]:
    rng = random.Random(seed)
    mapping: Dict[str, str] = {}
    fake_company = config.anonymize.fake_company_name

    # Step 1: Detect primary company from first 200 lines
    lines = text.splitlines()
    first_lines = "\n".join(lines[:200])
    doc_head = nlp(first_lines)

    org_counts = Counter([ent.text.strip() for ent in doc_head.ents if ent.label_ == "ORG" and len(ent.text.strip()) > 3 and ent.text.strip().lower() not in GENERIC_WORDS])
    # Ignore generic regulator orgs
    for reg in ["SEC", "Securities and Exchange Commission", "FASB", "IRS", "PCAOB"]:
        org_counts.pop(reg, None)

    target_company = org_counts.most_common(1)[0][0] if org_counts else "Amazon.com, Inc."
    target_clean = re.sub(r'[\.,]', '', target_company).strip()
    target_words = [w for w in target_clean.split() if w.lower() not in ("inc", "corp", "corporation", "ltd", "llc", "company", "com")]
    primary_word = target_words[0] if target_words else target_clean

    mapping[target_company] = fake_company
    if primary_word and len(primary_word) > 3 and primary_word.lower() not in GENERIC_WORDS:
        mapping[primary_word] = fake_company.split()[0] # e.g. "Aldervane"

    # Step 2: Remove PII (URLs, emails, phones, addresses)
    text = remove_pii(text)

    # Step 3: Run spaCy NER over full text (chunked for efficiency)
    full_doc = nlp(text[:250000]) # NER on representative portion
    other_orgs = []
    persons = []

    for ent in full_doc.ents:
        t = ent.text.strip()
        if len(t) < 3 or t in mapping or re.search(r'\d', t) or t.lower() in GENERIC_WORDS:
            continue
        if ent.label_ == "ORG":
            if t not in other_orgs and primary_word.lower() not in t.lower():
                other_orgs.append(t)
        elif ent.label_ == "PERSON":
            if t not in persons and not any(r.lower() in t.lower() for r in ROLES):
                persons.append(t)

    # Assign replacement names
    org_letters = [chr(i) for i in range(ord('A'), ord('Z') + 1)]
    for idx, org in enumerate(other_orgs[:26]):
        mapping[org] = f"Company {org_letters[idx]}"

    for idx, person in enumerate(persons[:26]):
        mapping[person] = f"Person {org_letters[idx]}"

    # Step 4: Scale numbers
    scale_factor = get_scale_factor(rng, config.anonymize.scale_factor_range)
    scaled_text = scale_amounts_and_shares(text, scale_factor)

    # Step 5: Replace entities in descending order of length to prevent substring clashes
    anonymized_text = scaled_text
    sorted_entities = sorted(mapping.keys(), key=lambda x: len(x), reverse=True)
    for orig in sorted_entities:
        replacement = mapping[orig]
        pattern = re.compile(rf'\b{re.escape(orig)}\b', re.IGNORECASE)
        anonymized_text = pattern.sub(replacement, anonymized_text)

    mapping_metadata = {
        "report_id": report_id,
        "primary_company": target_company,
        "fake_company": fake_company,
        "scale_factor": scale_factor,
        "entity_replacements": mapping,
    }

    return anonymized_text, mapping_metadata

def run_stage(config: AppConfig, force: bool = False) -> List[Path]:
    raw_dir = Path(config.data.raw_dir)
    out_dir = Path(config.data.out_dir) / "01_anonymized"
    out_dir.mkdir(parents=True, exist_ok=True)

    nlp = spacy.load("en_core_web_sm", disable=["parser"])

    report_files = sorted(list(raw_dir.glob("*.txt")))
    if not report_files:
        raise FileNotFoundError(f"No .txt files found in {raw_dir}. Please convert HTML reports first.")

    output_files = []
    for idx, r_file in enumerate(report_files):
        report_id = r_file.stem
        out_txt = out_dir / f"{report_id}.txt"
        out_map = out_dir / f"{report_id}.mapping.json"

        if not force and out_txt.exists() and out_map.exists():
            output_files.append(out_txt)
            continue

        raw_text = r_file.read_text(encoding="utf-8", errors="replace")
        anon_text, metadata = anonymize_report(
            text=raw_text,
            nlp=nlp,
            config=config,
            report_id=report_id,
            seed=config.seed + idx
        )

        out_txt.write_text(anon_text, encoding="utf-8")
        out_map.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        output_files.append(out_txt)

    return output_files
