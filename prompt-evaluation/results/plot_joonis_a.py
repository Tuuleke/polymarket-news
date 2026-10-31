"""
Joonis A — stacked bar chart: per-model aggregate scores broken down by criterion.
"""
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

CSV = Path(__file__).parent / "web_eval_20260423T094539Z.csv"

# ── Load data ──────────────────────────────────────────────────────────────────
criteria = ["grammar", "factual_consistency", "clarity", "relevance", "format"]
label_map = {
    "grammar": "Grammar",
    "factual_consistency": "Factual",
    "clarity": "Clarity",
    "relevance": "Relevance",
    "format": "Format",
}
model_map = {
    "deepseek/deepseek-v3.2":        "DeepSeek",
    "google/gemini-3-flash-preview":  "Gemini",
    "minimax/minimax-m2.7":           "MiniMax",
}

sums   = {m: {c: 0.0 for c in criteria} for m in model_map}
counts = {m: 0 for m in model_map}

with open(CSV, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        m = row["writer_model"]
        if m not in model_map:
            continue
        for c in criteria:
            sums[m][c] += float(row[c])
        counts[m] += 1

avgs = {
    model_map[m]: {c: sums[m][c] / counts[m] for c in criteria}
    for m in model_map
}
totals = {model: sum(avgs[model].values()) for model in avgs}

# Display order: highest to lowest total
models_ordered = sorted(avgs.keys(), key=lambda m: totals[m], reverse=True)

# ── Colour palette ─────────────────────────────────────────────────────────────
palette = {
    "Grammar":   "#4f86c6",   # blue
    "Factual":   "#e05c5c",   # red
    "Clarity":   "#5cba7a",   # green
    "Relevance": "#f0a830",   # amber
    "Format":    "#9b7fd4",   # violet
}

# ── Plot ───────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7, 5))
fig.patch.set_facecolor("#fafafa")
ax.set_facecolor("#fafafa")

x = np.arange(len(models_ordered))
bar_width = 0.52

bottoms = np.zeros(len(models_ordered))
for c in criteria:
    label = label_map[c]
    values = np.array([avgs[m][c] for m in models_ordered])
    bars = ax.bar(
        x, values,
        width=bar_width,
        bottom=bottoms,
        color=palette[label],
        label=label,
        edgecolor="white",
        linewidth=0.6,
    )
    # Segment label (hide if segment too small)
    for rect, val in zip(bars, values):
        if val >= 0.6:
            ax.text(
                rect.get_x() + rect.get_width() / 2,
                rect.get_y() + rect.get_height() / 2,
                f"{val:.1f}",
                ha="center", va="center",
                fontsize=8, color="white", fontweight="bold",
            )
    bottoms += values

# Total score label on top of each bar
for i, model in enumerate(models_ordered):
    ax.text(
        i, totals[model] + 0.4,
        f"{totals[model]:.1f}",
        ha="center", va="bottom",
        fontsize=10, fontweight="bold", color="#1a1a2e",
    )

# ── Axes styling ───────────────────────────────────────────────────────────────
ax.set_xticks(x)
ax.set_xticklabels(models_ordered, fontsize=11)
ax.set_ylabel("Average score (sum of criteria)", fontsize=10)
ax.set_ylim(0, 42)
ax.set_yticks(range(0, 43, 5))
ax.yaxis.grid(True, color="white", linewidth=1.2, zorder=0)
ax.set_axisbelow(True)
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)
ax.spines["left"].set_color("#cccccc")
ax.spines["bottom"].set_color("#cccccc")
ax.tick_params(axis="both", length=0, labelsize=10)

# Max possible score reference line
ax.axhline(40, color="#bbbbbb", linestyle="--", linewidth=0.8, zorder=0)
ax.text(len(models_ordered) - 0.5, 40.3, "max 40", fontsize=8, color="#999999")

# Legend
legend_patches = [
    mpatches.Patch(color=palette[label_map[c]], label=label_map[c])
    for c in criteria
]
ax.legend(
    handles=legend_patches,
    loc="upper right",
    frameon=True,
    framealpha=0.9,
    edgecolor="#dddddd",
    fontsize=9,
    title="Criterion",
    title_fontsize=9,
)

ax.set_title(
    "Mudelite koondskoorid kriteeriumide kaupa",
    fontsize=12, fontweight="bold", pad=14, color="#1a1a2e",
)

plt.tight_layout()
out = Path(__file__).parent / "joonis_a.png"
plt.savefig(out, dpi=180, bbox_inches="tight")
print(f"Saved → {out}")
plt.show()
