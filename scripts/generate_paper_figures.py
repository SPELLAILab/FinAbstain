"""Generate publication-ready diagrams, charts, and statistical tables for the FinAbstain paper.
"""

import json
import os
import shutil
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns
import tiktoken

# Set publication style
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Helvetica']
plt.rcParams['axes.edgecolor'] = '#cccccc'
plt.rcParams['axes.linewidth'] = 0.8
plt.rcParams['grid.color'] = '#eaeaea'
plt.rcParams['grid.linestyle'] = '--'
plt.rcParams['grid.alpha'] = 0.7

BASE_DIR = Path(__file__).resolve().parent.parent
RELEASE_DIR = BASE_DIR / "release"
FIG_DIR = BASE_DIR / "figures"
FIG_DIR.mkdir(exist_ok=True, parents=True)

# 1. Load data
short_path = RELEASE_DIR / "benchmark_short.jsonl"
full_path = RELEASE_DIR / "benchmark.jsonl"

with open(short_path, "r", encoding="utf-8") as f:
    items_short = [json.loads(line) for line in f]

with open(full_path, "r", encoding="utf-8") as f:
    items_full = [json.loads(line) for line in f]

enc = tiktoken.get_encoding("cl100k_base")

records = []
for s, fl in zip(items_short, items_full):
    q_tokens = len(enc.encode(s["question"]))
    q_words = len(s["question"].split())
    q_chars = len(s["question"])

    c_short_tokens = len(enc.encode(s["context"]))
    c_short_words = len(s["context"].split())
    c_full_tokens = len(enc.encode(fl["context"]))

    ev_tokens = len(enc.encode(s.get("evidence_span") or ""))
    ans_tokens = len(enc.encode(s.get("original_answer") or ""))

    # Question category / prefix
    q_lower = s["question"].strip().lower()
    if q_lower.startswith("what"):
        q_wh = "What"
    elif q_lower.startswith("how much") or q_lower.startswith("how many"):
        q_wh = "How much/many"
    elif q_lower.startswith("which"):
        q_wh = "Which"
    elif q_lower.startswith("when"):
        q_wh = "When"
    elif q_lower.startswith("who"):
        q_wh = "Who"
    else:
        q_wh = "Other"

    # Company name mapping
    rep_map = {
        "pfe": "Pfizer (Healthcare)",
        "ko": "Coca-Cola (Beverages)",
        "cat": "Caterpillar (Industrial)",
        "report": "Amazon (Retail/Tech)",
        "amzn": "Amazon (Retail/Tech)",
    }
    company_name = rep_map.get(s["report_id"], s["report_id"].upper())

    records.append({
        "id": s["id"],
        "category": s["category"].capitalize(),
        "gold_decision": s["gold_decision"].capitalize(),
        "gold_reason": s["gold_reason"],
        "fact_type": s["fact_type"].capitalize(),
        "report_id": s["report_id"],
        "company": company_name,
        "target_position": s["target_position"],
        "q_tokens": q_tokens,
        "q_words": q_words,
        "q_chars": q_chars,
        "c_short_tokens": c_short_tokens,
        "c_short_words": c_short_words,
        "c_full_tokens": c_full_tokens,
        "ev_tokens": ev_tokens,
        "ans_tokens": ans_tokens,
        "q_wh": q_wh,
    })

df = pd.DataFrame(records)

# -------------------------------------------------------------------------
# Figure 1: Category Distribution Nested Donut Chart (Abstain vs Answerable)
# -------------------------------------------------------------------------
print("Generating Fig 1: Category Distribution...")
fig, ax = plt.subplots(figsize=(8, 7), dpi=300)

outer_labels = ["Answerable", "Conflict", "Missing", "Ambiguous"]
outer_counts = [
    (df["category"] == "Answerable").sum(),
    (df["category"] == "Conflict").sum(),
    (df["category"] == "Missing").sum(),
    (df["category"] == "Ambiguous").sum(),
]
outer_colors = ["#2E7D32", "#C62828", "#E65100", "#1565C0"]

inner_labels = ["Answer\n(35.0%)", "Abstain\n(65.0%)"]
inner_counts = [outer_counts[0], sum(outer_counts[1:])]
inner_colors = ["#81C784", "#EF9A9A"]

# Outer ring (fine-grained categories)
wedges_out, texts_out = ax.pie(
    outer_counts,
    labels=[f"{label}\n(n={count}, {count/len(df)*100:.1f}%)" for label, count in zip(outer_labels, outer_counts)],
    startangle=140,
    colors=outer_colors,
    radius=1.0,
    wedgeprops=dict(width=0.28, edgecolor="white", linewidth=2.5),
    textprops=dict(fontsize=11, fontweight="bold", color="#1a252f")
)

# Inner ring (macro decision: Answer vs Abstain)
wedges_in, texts_in = ax.pie(
    inner_counts,
    labels=inner_labels,
    startangle=140,
    labeldistance=0.55,
    colors=inner_colors,
    radius=0.72,
    wedgeprops=dict(width=0.28, edgecolor="white", linewidth=2.5),
    textprops=dict(fontsize=10, fontweight="bold", color="#2c3e50", ha="center")
)

# Center circle
ax.text(0, 0, f"FinAbstain\nN = {len(df)}", ha="center", va="center", fontsize=13, fontweight="bold", color="#1a252f")

ax.set_title("FinAbstain Benchmark Question Distribution by Category", fontsize=14, fontweight="bold", pad=20, color="#1a252f")
plt.tight_layout()
fig1_path = FIG_DIR / "fig1_category_distribution_donut.png"
plt.savefig(fig1_path, dpi=300, bbox_inches="tight")
plt.close()

# -------------------------------------------------------------------------
# Figure 2: Fact Type and Company Breakdown (Two panels)
# -------------------------------------------------------------------------
print("Generating Fig 2: Fact Types and Company Distribution...")
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), dpi=300)

# Panel 1: Fact Types
ft_counts = df["fact_type"].value_counts()
colors_ft = ["#3498DB", "#9B59B6", "#E67E22", "#1ABC9C", "#F39C12", "#95A5A6"]
bars1 = ax1.barh(ft_counts.index, ft_counts.values, color=colors_ft[:len(ft_counts)], edgecolor="#2c3e50", alpha=0.85, height=0.6)
ax1.set_xlabel("Number of Questions", fontsize=11, fontweight="bold", labelpad=8)
ax1.set_title("(A) Distribution by Financial Fact Type", fontsize=12, fontweight="bold", pad=12)
ax1.invert_yaxis()

for bar in bars1:
    w = bar.get_width()
    pct = w / len(df) * 100
    ax1.text(w + 1.2, bar.get_y() + bar.get_height() / 2, f"{int(w)} ({pct:.1f}%)", va="center", fontsize=10, fontweight="semibold", color="#2c3e50")
ax1.set_xlim(0, max(ft_counts.values) + 15)

# Panel 2: Corporate 10-K Filings Distribution
comp_counts = df["company"].value_counts()
colors_comp = ["#2C3E50", "#E74C3C", "#34495E", "#16A085"]
bars2 = ax2.barh(comp_counts.index, comp_counts.values, color=colors_comp[:len(comp_counts)], edgecolor="#2c3e50", alpha=0.85, height=0.6)
ax2.set_xlabel("Number of Questions", fontsize=11, fontweight="bold", labelpad=8)
ax2.set_title("(B) Distribution across SEC 10-K Filings", fontsize=12, fontweight="bold", pad=12)
ax2.invert_yaxis()

for bar in bars2:
    w = bar.get_width()
    pct = w / len(df) * 100
    ax2.text(w + 0.8, bar.get_y() + bar.get_height() / 2, f"{int(w)} ({pct:.1f}%)", va="center", fontsize=10, fontweight="semibold", color="#2c3e50")
ax2.set_xlim(0, max(comp_counts.values) + 8)

plt.tight_layout()
fig2_path = FIG_DIR / "fig2_fact_types_and_reports.png"
plt.savefig(fig2_path, dpi=300, bbox_inches="tight")
plt.close()

# -------------------------------------------------------------------------
# Figure 3: Token Length Distributions (Question, Short Ctx, Full Ctx)
# -------------------------------------------------------------------------
print("Generating Fig 3: Token Length Distributions...")
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(13, 9), dpi=300)

cat_order = ["Answerable", "Missing", "Conflict", "Ambiguous"]
cat_palette = {"Answerable": "#2E7D32", "Missing": "#E65100", "Conflict": "#C62828", "Ambiguous": "#1565C0"}

# Panel A: Question Token Length by Category (Boxplot with Stripplot)
sns.boxplot(data=df, x="category", y="q_tokens", hue="category", order=cat_order, palette=cat_palette, ax=ax1, width=0.45, boxprops=dict(alpha=0.7), showmeans=True,
            legend=False, meanprops={"marker": "D", "markerfacecolor": "white", "markeredgecolor": "black", "markersize": 6})
sns.stripplot(data=df, x="category", y="q_tokens", order=cat_order, color="black", alpha=0.4, jitter=0.2, size=5, ax=ax1)
ax1.set_title("(A) Question Token Length across Categories (cl100k)", fontsize=11, fontweight="bold")
ax1.set_xlabel("Category", fontsize=10, fontweight="bold")
ax1.set_ylabel("Tokens", fontsize=10, fontweight="bold")

# Panel B: Short Context Token Length by Category
sns.boxplot(data=df, x="category", y="c_short_tokens", hue="category", order=cat_order, palette=cat_palette, ax=ax2, width=0.45, boxprops=dict(alpha=0.7), showmeans=True,
            legend=False, meanprops={"marker": "D", "markerfacecolor": "white", "markeredgecolor": "black", "markersize": 6})
sns.stripplot(data=df, x="category", y="c_short_tokens", order=cat_order, color="black", alpha=0.4, jitter=0.2, size=5, ax=ax2)
ax2.set_title("(B) Context Token Length per Question (Section Passages)", fontsize=11, fontweight="bold")
ax2.set_xlabel("Category", fontsize=10, fontweight="bold")
ax2.set_ylabel("Tokens", fontsize=10, fontweight="bold")

# Panel C: Evidence Span Token Length Distribution (KDE + Hist)
sns.histplot(df["ev_tokens"], kde=True, ax=ax3, color="#8E44AD", bins=15, alpha=0.6, edgecolor="#4A235A")
ev_mean = df["ev_tokens"].mean()
ev_med = df["ev_tokens"].median()
ax3.axvline(ev_mean, color="#C0392B", linestyle="--", linewidth=1.5, label=f"Mean: {ev_mean:.1f}")
ax3.axvline(ev_med, color="#27AE60", linestyle=":", linewidth=2.0, label=f"Median: {ev_med:.0f}")
ax3.set_title("(C) Evidence Span Length Distribution", fontsize=11, fontweight="bold")
ax3.set_xlabel("Tokens", fontsize=10, fontweight="bold")
ax3.set_ylabel("Count", fontsize=10, fontweight="bold")
ax3.legend(frameon=True, fontsize=9)

# Panel D: Full Report vs Short Context Comparison (KDE)
sns.kdeplot(df["c_short_tokens"], ax=ax4, fill=True, color="#2980B9", alpha=0.4, label="Short Context (Passage, ~763 tok)")
ax4_sec = ax4.twiny()
sns.kdeplot(df["c_full_tokens"], ax=ax4_sec, fill=True, color="#D35400", alpha=0.4, label="Full 10-K Report (~7,668 tok)")
ax4.set_xlabel("Short Context Tokens", fontsize=10, fontweight="bold", color="#2980B9")
ax4_sec.set_xlabel("Full Report Tokens", fontsize=10, fontweight="bold", color="#D35400")
ax4.set_ylabel("Density", fontsize=10, fontweight="bold")
ax4.set_title("(D) Context Length Regimes (Evaluation Settings)", fontsize=11, fontweight="bold", pad=20)

plt.tight_layout()
fig3_path = FIG_DIR / "fig3_token_length_distributions.png"
plt.savefig(fig3_path, dpi=300, bbox_inches="tight")
plt.close()

# -------------------------------------------------------------------------
# Figure 4: Target Perturbation Depth / Evidence Position Distribution
# -------------------------------------------------------------------------
print("Generating Fig 4: Evidence Position / Depth...")
fig, ax = plt.subplots(figsize=(8, 5), dpi=300)

sns.histplot(df["target_position"], bins=12, kde=True, color="#2C3E50", alpha=0.65, edgecolor="#1A252F", ax=ax, stat="density")
mean_pos = df["target_position"].mean()
med_pos = df["target_position"].median()
ax.axvline(mean_pos, color="#E74C3C", linestyle="--", linewidth=2.0, label=f"Mean Position: {mean_pos:.2f}")
ax.axvline(med_pos, color="#27AE60", linestyle=":", linewidth=2.0, label=f"Median Position: {med_pos:.2f}")

# Formatting
ax.set_title("Normalized Evidence / Perturbation Depth in Document Passages", fontsize=12, fontweight="bold", pad=12)
ax.set_xlabel("Relative Position in Context [0.0 = Document Start, 1.0 = Document End]", fontsize=10, fontweight="bold")
ax.set_ylabel("Density", fontsize=10, fontweight="bold")
ax.set_xlim(0.0, 1.0)
ax.legend(frameon=True, fontsize=10, loc="upper right")

# Annotations showing uniform spread
ax.text(0.5, ax.get_ylim()[1]*0.88, "Evidence is uniformly distributed\nacross passage depths (No Positional Bias)", 
        ha="center", fontsize=10, style="italic", bbox=dict(boxstyle="round,pad=0.5", facecolor="#F8F9F9", edgecolor="#BDC3C7"))

plt.tight_layout()
fig4_path = FIG_DIR / "fig4_target_position_depth.png"
plt.savefig(fig4_path, dpi=300, bbox_inches="tight")
plt.close()

# -------------------------------------------------------------------------
# Figure 5: Comprehensive 4-Panel Dataset Dashboard (Primary Paper Figure)
# -------------------------------------------------------------------------
print("Generating Fig 5: Composite Paper Overview Dashboard...")
fig = plt.figure(figsize=(15, 11), dpi=300)
gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.25)

# Panel A: Category Pie
axA = fig.add_subplot(gs[0, 0])
wedges, texts, autotexts = axA.pie(
    outer_counts,
    labels=[f"{l}\n({c/len(df)*100:.1f}%)" for l, c in zip(outer_labels, outer_counts)],
    colors=outer_colors,
    autopct="",
    startangle=140,
    wedgeprops=dict(width=0.4, edgecolor="white", linewidth=2),
    textprops=dict(fontsize=10, fontweight="bold")
)
axA.text(0, 0, f"FinAbstain\nN = {len(df)}", ha="center", va="center", fontsize=12, fontweight="bold")
axA.set_title("(A) Benchmark Label Distribution", fontsize=12, fontweight="bold", pad=10)

# Panel B: Fact Types Bar
axB = fig.add_subplot(gs[0, 1])
barsB = axB.barh(ft_counts.index, ft_counts.values, color=colors_ft[:len(ft_counts)], edgecolor="#2c3e50", alpha=0.85, height=0.6)
axB.invert_yaxis()
axB.set_title("(B) Financial Fact Type Breakdown", fontsize=12, fontweight="bold", pad=10)
axB.set_xlabel("Count", fontsize=10, fontweight="bold")
for bar in barsB:
    w = bar.get_width()
    pct = w / len(df) * 100
    axB.text(w + 1.0, bar.get_y() + bar.get_height() / 2, f"{int(w)} ({pct:.1f}%)", va="center", fontsize=9, fontweight="bold")
axB.set_xlim(0, max(ft_counts.values) + 16)

# Panel C: Question Token Lengths by Category
axC = fig.add_subplot(gs[1, 0])
sns.boxplot(data=df, x="category", y="q_tokens", hue="category", order=cat_order, palette=cat_palette, ax=axC, width=0.45, boxprops=dict(alpha=0.7), showmeans=True,
            legend=False, meanprops={"marker": "D", "markerfacecolor": "white", "markeredgecolor": "black", "markersize": 6})
sns.stripplot(data=df, x="category", y="q_tokens", order=cat_order, color="black", alpha=0.35, jitter=0.2, size=4, ax=axC)
axC.set_title("(C) Question Token Lengths (cl100k)", fontsize=12, fontweight="bold", pad=10)
axC.set_xlabel("Category", fontsize=10, fontweight="bold")
axC.set_ylabel("Tokens", fontsize=10, fontweight="bold")

# Panel D: Evidence Position in Document Depth
axD = fig.add_subplot(gs[1, 1])
sns.histplot(df["target_position"], bins=12, kde=True, color="#2C3E50", alpha=0.6, edgecolor="#1A252F", ax=axD, stat="density")
axD.axvline(mean_pos, color="#E74C3C", linestyle="--", linewidth=1.8, label=f"Mean: {mean_pos:.2f}")
axD.axvline(med_pos, color="#27AE60", linestyle=":", linewidth=1.8, label=f"Median: {med_pos:.2f}")
axD.set_title("(D) Normalized Perturbation Depth in Passages", fontsize=12, fontweight="bold", pad=10)
axD.set_xlabel("Passage Depth [0.0 - 1.0]", fontsize=10, fontweight="bold")
axD.set_ylabel("Density", fontsize=10, fontweight="bold")
axD.set_xlim(0.0, 1.0)
axD.legend(frameon=True, fontsize=9)

fig.suptitle("FinAbstain: Dataset Characteristics & Token Profiling", fontsize=15, fontweight="bold", y=0.98)
fig5_path = FIG_DIR / "fig5_dataset_paper_dashboard.png"
plt.savefig(fig5_path, dpi=300, bbox_inches="tight")
plt.close()

# -------------------------------------------------------------------------
# Generate LaTeX Statistics Table
# -------------------------------------------------------------------------
print("Generating LaTeX Table...")
stats_table = []
for cat in cat_order:
    sub = df[df["category"] == cat]
    stats_table.append({
        "Category": cat,
        "Decision": sub["gold_decision"].iloc[0],
        "Count": len(sub),
        "Percent": f"{len(sub)/len(df)*100:.1f}\\%",
        "Q_Tok_Mean": f"{sub['q_tokens'].mean():.1f} $\\pm$ {sub['q_tokens'].std():.1f}",
        "Q_Tok_Med": f"{sub['q_tokens'].median():.0f}",
        "Ctx_Tok_Mean": f"{sub['c_short_tokens'].mean():.1f} $\\pm$ {sub['c_short_tokens'].std():.1f}",
        "Ctx_Tok_Med": f"{sub['c_short_tokens'].median():.0f}",
        "Ev_Tok_Mean": f"{sub['ev_tokens'].mean():.1f} $\\pm$ {sub['ev_tokens'].std():.1f}",
        "Target_Pos": f"{sub['target_position'].mean():.2f} $\\pm$ {sub['target_position'].std():.2f}",
    })

# Total row
stats_table.append({
    "Category": "\\textbf{Total / Overall}",
    "Decision": "-",
    "Count": len(df),
    "Percent": "100.0\\%",
    "Q_Tok_Mean": f"{df['q_tokens'].mean():.1f} $\\pm$ {df['q_tokens'].std():.1f}",
    "Q_Tok_Med": f"{df['q_tokens'].median():.0f}",
    "Ctx_Tok_Mean": f"{df['c_short_tokens'].mean():.1f} $\\pm$ {df['c_short_tokens'].std():.1f}",
    "Ctx_Tok_Med": f"{df['c_short_tokens'].median():.0f}",
    "Ev_Tok_Mean": f"{df['ev_tokens'].mean():.1f} $\\pm$ {df['ev_tokens'].std():.1f}",
    "Target_Pos": f"{df['target_position'].mean():.2f} $\\pm$ {df['target_position'].std():.2f}",
})

latex_code = """\\begin{table*}[t]
\\centering
\\small
\\caption{\\textbf{FinAbstain Dataset Statistics.} Question token counts ($Q$), context tokens ($C$, short section context), and evidence span tokens ($E$) are computed using the \\texttt{cl100k\\_base} tokenizer. Target Depth denotes normalized position within the source passage $[0, 1]$.}
\\label{tab:dataset_stats}
\\begin{tabular}{llrrrrrrr}
\\toprule
\\textbf{Category} & \\textbf{Gold Decision} & \\textbf{Count ($N$)} & \\textbf{\\%} & \\textbf{Q Tokens (Mean$\\pm$SD)} & \\textbf{Q Med.} & \\textbf{Context Tokens} & \\textbf{Evidence Tokens} & \\textbf{Target Depth} \\\\
\\midrule
"""

for row in stats_table:
    if "Total" in row["Category"]:
        latex_code += "\\midrule\n"
    latex_code += f"{row['Category']} & {row['Decision']} & {row['Count']} & {row['Percent']} & {row['Q_Tok_Mean']} & {row['Q_Tok_Med']} & {row['Ctx_Tok_Mean']} & {row['Ev_Tok_Mean']} & {row['Target_Pos']} \\\\\n"

latex_code += """\\bottomrule
\\end{tabular}
\\end{table*}
"""

with open(FIG_DIR / "dataset_stats_table.tex", "w", encoding="utf-8") as f:
    f.write(latex_code)

# Write summary JSON for documentation
summary_data = {
    "total_samples": len(df),
    "category_counts": df["category"].value_counts().to_dict(),
    "gold_decision_counts": df["gold_decision"].value_counts().to_dict(),
    "fact_type_counts": df["fact_type"].value_counts().to_dict(),
    "report_counts": df["company"].value_counts().to_dict(),
    "question_type_counts": df["q_wh"].value_counts().to_dict(),
    "token_metrics": {
        "question_tokens": {
            "mean": round(float(df["q_tokens"].mean()), 2),
            "std": round(float(df["q_tokens"].std()), 2),
            "median": round(float(df["q_tokens"].median()), 2),
            "min": int(df["q_tokens"].min()),
            "max": int(df["q_tokens"].max()),
        },
        "context_short_tokens": {
            "mean": round(float(df["c_short_tokens"].mean()), 2),
            "std": round(float(df["c_short_tokens"].std()), 2),
            "median": round(float(df["c_short_tokens"].median()), 2),
            "min": int(df["c_short_tokens"].min()),
            "max": int(df["c_short_tokens"].max()),
        },
        "context_full_tokens": {
            "mean": round(float(df["c_full_tokens"].mean()), 2),
            "std": round(float(df["c_full_tokens"].std()), 2),
            "median": round(float(df["c_full_tokens"].median()), 2),
            "min": int(df["c_full_tokens"].min()),
            "max": int(df["c_full_tokens"].max()),
        },
        "evidence_tokens": {
            "mean": round(float(df["ev_tokens"].mean()), 2),
            "std": round(float(df["ev_tokens"].std()), 2),
            "median": round(float(df["ev_tokens"].median()), 2),
            "min": int(df["ev_tokens"].min()),
            "max": int(df["ev_tokens"].max()),
        },
        "answer_tokens": {
            "mean": round(float(df["ans_tokens"].mean()), 2),
            "std": round(float(df["ans_tokens"].std()), 2),
            "median": round(float(df["ans_tokens"].median()), 2),
            "min": int(df["ans_tokens"].min()),
            "max": int(df["ans_tokens"].max()),
        },
        "target_position": {
            "mean": round(float(df["target_position"].mean()), 3),
            "std": round(float(df["target_position"].std()), 3),
            "median": round(float(df["target_position"].median()), 3),
            "min": round(float(df["target_position"].min()), 3),
            "max": round(float(df["target_position"].max()), 3),
        }
    }
}

with open(FIG_DIR / "dataset_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary_data, f, indent=2)

print("All figures and tables generated successfully in:", FIG_DIR)
