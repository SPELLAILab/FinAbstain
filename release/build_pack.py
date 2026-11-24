"""Build blind human-annotation packs for FinAbstain (Word items + Excel answers + guidelines).

  python build_finabstain_pack.py sample   -> annotation_pack/samples/
  python build_finabstain_pack.py full     -> annotation_pack/annotator_1, annotator_2, researcher_only

Annotators see the UNPADDED edited section (benchmark_short.jsonl), never the gold label,
company, source id or edit metadata. Each annotator gets the same blind IDs in a different order.
"""
import csv, json, random, re, sys
from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

BASE_DIR = Path(__file__).resolve().parent
SRC = BASE_DIR / "benchmark_short.jsonl"
OUT = BASE_DIR / "annotation_pack"
SEED = 2027
QUOTA = {"ambiguous": 22, "conflict": 20, "missing": 15, "answerable": 15}
FULL_QUOTA = {"ambiguous": 22, "conflict": 38, "missing": 33, "answerable": 50}  # every item in the benchmark
SAMPLE_QUOTA = {"ambiguous": 2, "conflict": 2, "missing": 1, "answerable": 1}

LABELS = ["Answerable", "Missing", "Conflict", "Ambiguous"]
LABEL_KEY = {"answerable": "Answerable", "missing": "Missing", "conflict": "Conflict", "ambiguous": "Ambiguous"}
CONF = ["1 (guessing)", "2 (fairly sure)", "3 (certain)"]
NAT = ["1", "2", "3", "4", "5"]
QUAL = ["Clear", "Flawed"]

DEFS = [
    ("Answerable", "The passage states exactly one value or fact that answers the question, with no competing value."),
    ("Missing", "The passage is about the topic of the question, but the specific fact requested is not stated anywhere in it."),
    ("Conflict", "The passage gives two or more different values for the SAME fact (same metric, same entity, same period) "
                 "and nothing says which is correct."),
    ("Ambiguous", "The question does not say enough to pick one answer. The passage holds more than one valid answer "
                  "depending on a period, segment, unit or entity that the question does not specify."),
]
RULES = [
    "Use only the passage. Do not use outside knowledge about the real company, its filings or its numbers.",
    "Names are replaced with placeholders (Company A, Person B) and money amounts are rescaled. Do not judge whether a "
    "number looks realistic, and do not try to work out which company it is.",
    "Read the question first, then the passage, then choose one label.",
    "Every item has exactly one correct label. If two seem possible, use the tie-breakers below and lower your confidence.",
    "Some passages are cut from a longer report and may start or end mid-sentence. That is not an error and not a reason to choose Missing.",
    "Work alone. Do not discuss items with the other annotator until both sheets are submitted.",
]
TIEBREAK = [
    "Conflict vs Ambiguous: if the passage gives different values for the same period, entity and segment that the question "
    "names, choose Conflict. If the values differ because they belong to different periods, segments or entities that the "
    "question leaves open, choose Ambiguous.",
    "Missing vs Answerable: if the passage only gives a nearby figure (a different period, or a related metric) and not the "
    "requested one, choose Missing.",
    "Missing vs Ambiguous: choose Ambiguous only if at least two valid answers are actually present in the passage. "
    "If the question is vague but the passage contains no answer at all, choose Missing.",
    "If the same value is repeated identically in two places, that is not a conflict. Choose Answerable.",
]
DONT = [
    "Do not guess how the passage was made or look for signs of editing when choosing the label.",
    "Do not choose Conflict just because a number appears twice with different wording. Check it is the same fact.",
    "Do not choose Missing because a passage begins or ends abruptly.",
    "Do not leave the label blank. If unsure, pick your best label, give confidence 1, and add a note.",
]
EXTRA = [
    ("Confidence", "How sure are you of your label? 1 = guessing, 2 = fairly sure, 3 = certain."),
    ("Naturalness", "Does the passage read like ordinary text from a real annual report? 1 = clearly altered or artificial, "
                    "5 = entirely natural. Answer this for every item, whatever label you chose."),
    ("Question quality", "Clear = the question is well formed. Flawed = it is garbled, self-contradictory or cannot be "
                         "understood. This is separate from whether the question can be answered."),
    ("Note (optional)", "One line explaining any item you found hard, or what confused you."),
]


# ------------------------------------------------------------------ data
def load_items():
    return [json.loads(l) for l in open(SRC, encoding="utf-8")]


def pick(items, quota, rng):
    chosen = []
    for cat, n in quota.items():
        pool = [x for x in items if x["category"] == cat]
        chosen += rng.sample(pool, n)
    return chosen


def clean(txt):
    txt = txt.replace(" ", " ")
    txt = re.sub(r"(?m)^\s*[•·]\s*\n+", "\u2022 ", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt.strip())
    return txt


def leak_check(items):
    bad = re.compile(r"\b(edit|inserted|gold|abstain|missing|conflict|ambiguous)\b", re.I)
    hits = [x["id"] for x in items if bad.search(x["question"])]
    return hits


# ------------------------------------------------------------------ docx helpers
def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def borders(cell, color="808080", sz=6):
    tcPr = cell._tc.get_or_add_tcPr()
    b = OxmlElement("w:tcBorders")
    for side in ("top", "left", "bottom", "right"):
        e = OxmlElement(f"w:{side}")
        e.set(qn("w:val"), "single"); e.set(qn("w:sz"), str(sz)); e.set(qn("w:color"), color)
        b.append(e)
    tcPr.append(b)


def divider(doc):
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    bd = OxmlElement("w:pBdr")
    e = OxmlElement("w:bottom")
    e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "8"); e.set(qn("w:space"), "1"); e.set(qn("w:color"), "999999")
    bd.append(e); pPr.append(bd)
    p.paragraph_format.space_after = Pt(6)


def base_doc():
    d = Document()
    st = d.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10.5)
    for s in d.sections:
        s.left_margin = s.right_margin = Pt(54); s.top_margin = s.bottom_margin = Pt(50)
    return d


def checks(doc, label, options, per_line=4):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(label + "  "); r.bold = True
    p.add_run("    ".join(f"☐ {o}" for o in options))
    return p


def write_items_doc(items, path, title):
    d = base_doc()
    h = d.add_heading(title, level=1)
    d.add_paragraph("Read the question, then the passage, then tick your answers under each item. Also enter every answer in the Excel sheet, which is the copy that gets scored.").italic = True
    for k, it in enumerate(items):
        divider(d)
        p = d.add_paragraph(); p.paragraph_format.keep_with_next = True
        r = p.add_run(f"Item {it['blind_id']}"); r.bold = True; r.font.size = Pt(12)
        q = d.add_paragraph(); q.paragraph_format.keep_with_next = True
        rq = q.add_run("Question: "); rq.bold = True
        q.add_run(it["question"].strip())
        t = d.add_table(rows=1, cols=1); c = t.rows[0].cells[0]
        shade(c, "F3F3F3"); borders(c)
        c.paragraphs[0].text = ""
        parts = clean(it["context"]).split("\n\n")
        first = True
        for part in parts:
            para = c.paragraphs[0] if first else c.add_paragraph()
            first = False
            run = para.add_run(part.strip()); run.font.size = Pt(9)
            para.paragraph_format.space_after = Pt(3)
        d.add_paragraph().paragraph_format.space_after = Pt(2)
        hd = d.add_paragraph(); hd.paragraph_format.keep_with_next = True
        hr = hd.add_run(f"Your answers for item {it['blind_id']}"); hr.bold = True; hr.font.size = Pt(10)
        blk = []
        blk.append(checks(d, "Label:", LABELS))
        blk.append(checks(d, "Confidence:", CONF))
        blk.append(checks(d, "Naturalness (1 = altered, 5 = natural):", NAT))
        blk.append(checks(d, "Question:", QUAL))
        n = d.add_paragraph(); n.add_run("Note: ").bold = True; n.add_run("_" * 70)
        blk.append(n)
        r = d.add_paragraph().add_run(f"Also enter these answers in the Excel row for item {it['blind_id']}.")
        r.italic = True; r.font.size = Pt(9)
        for para in blk[:-1]:
            para.paragraph_format.keep_with_next = True
    d.save(path)


def write_guidelines(path):
    d = base_doc()
    d.add_heading("Annotation Guidelines: Financial Question Answerability", level=1)
    d.add_paragraph("You will read short passages taken from annual reports (10-K filings) together with a question. "
                    "Decide whether the question can be answered from the passage alone, and if not, why not.")
    d.add_heading("Labels", level=2)
    t = d.add_table(rows=1, cols=2); t.style = "Table Grid"
    t.rows[0].cells[0].text = "Label"; t.rows[0].cells[1].text = "Meaning"
    for c in t.rows[0].cells:
        shade(c, "D9E2F3"); c.paragraphs[0].runs[0].bold = True
    for name, txt in DEFS:
        row = t.add_row().cells; row[0].text = name; row[1].text = txt
    d.add_heading("Core rules", level=2)
    for r in RULES:
        d.add_paragraph(r, style="List Number")
    d.add_heading("Tie-breakers", level=2)
    for r in TIEBREAK:
        d.add_paragraph(r, style="List Bullet")
    d.add_heading("Other questions per item", level=2)
    for n, txt in EXTRA:
        p = d.add_paragraph(style="List Bullet"); p.add_run(n + ": ").bold = True; p.add_run(txt)
    d.add_heading("Please do not", level=2)
    for r in DONT:
        d.add_paragraph(r, style="List Bullet")
    d.add_heading("Logistics", level=2)
    d.add_paragraph("Answer in the Excel file using the dropdowns. Do not change item IDs or reorder rows. "
                    "Expect about 2 minutes per item.")
    d.save(path)


def write_xlsx(items, path):
    wb = Workbook(); ws = wb.active; ws.title = "Answers"
    head = ["Item ID", "Label", "Confidence", "Naturalness (1-5)", "Question quality", "Note (optional)"]
    ws.append(head)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="305496")
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for it in items:
        ws.append([it["blind_id"], None, None, None, None, None])
    lists = wb.create_sheet("Lists")
    cols = {"A": LABELS, "B": CONF, "C": NAT, "D": QUAL}
    for col, vals in cols.items():
        for i, v in enumerate(vals, 1):
            lists[f"{col}{i}"] = v
    lists.sheet_state = "hidden"
    n = len(items) + 1
    for target, col, k in (("B", "A", len(LABELS)), ("C", "B", len(CONF)), ("D", "C", len(NAT)), ("E", "D", len(QUAL))):
        dv = DataValidation(type="list", formula1=f"=Lists!${col}$1:${col}${k}", allow_blank=True,
                            showErrorMessage=True, errorTitle="Invalid", error="Pick a value from the dropdown.")
        ws.add_data_validation(dv); dv.add(f"{target}2:{target}{n}")
    for col, w in zip("ABCDEF", (10, 14, 16, 18, 16, 60)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    wb.save(path)


def write_truth(items, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["blind_id", "true_label", "source_item_id", "report", "gold_decision", "validator_a", "validator_b"])
        for it in sorted(items, key=lambda x: x["blind_id"]):
            w.writerow([it["blind_id"], LABEL_KEY[it["category"]], it["id"], it["report_id"], it["gold_decision"],
                        (it.get("validator_a") or {}).get("label"), (it.get("validator_b") or {}).get("label")])


# ------------------------------------------------------------------ main
def main(mode):
    rng = random.Random(SEED)
    items = load_items()
    quota = SAMPLE_QUOTA if mode == "sample" else FULL_QUOTA if mode == "complete" else QUOTA
    chosen = pick(items, quota, rng)
    ids = rng.sample(range(100, 1000), len(chosen))
    for it, i in zip(chosen, ids):
        it["blind_id"] = f"F{i}"
    assert len({x["blind_id"] for x in chosen}) == len(chosen)
    leaks = leak_check(chosen)
    if leaks:
        print("WARNING question text contains label words:", leaks)
    if mode == "sample":
        base = OUT / "samples"; base.mkdir(parents=True, exist_ok=True)
        order = chosen[:]; rng.shuffle(order)
        write_items_doc(order, base / "items_SAMPLE.docx", "FinAbstain Annotation: SAMPLE")
        write_xlsx(order, base / "answers_SAMPLE.xlsx")
        write_guidelines(base / "Guidelines.docx")
        write_truth(chosen, base / "ground_truth_HIDDEN_SAMPLE.csv")
        print("sample written", base); return
    (OUT / "researcher_only").mkdir(parents=True, exist_ok=True)
    write_guidelines(OUT / "Guidelines.docx")
    write_truth(chosen, OUT / "researcher_only" / "ground_truth_HIDDEN.csv")
    for k in (1, 2):
        order = chosen[:]; random.Random(SEED + k).shuffle(order)
        d = OUT / f"annotator_{k}"; d.mkdir(exist_ok=True)
        write_items_doc(order, d / "items.docx", "FinAbstain Annotation Items")
        write_xlsx(order, d / "answers.xlsx")
    import collections
    print("items", len(chosen), collections.Counter(x["category"] for x in chosen))
    print("reports", collections.Counter(x["report_id"] for x in chosen))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "sample")
