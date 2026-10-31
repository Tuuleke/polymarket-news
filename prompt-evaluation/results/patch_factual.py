"""
Replace factual_consistency in the CSV with grounded scores from the JSON,
then recalculate the total column. Rows with no grounded entry are left unchanged.
"""
import csv, json
from pathlib import Path

base = Path(__file__).parent

with open(base / "grounded_eval_results.json") as f:
    grounded = json.load(f)

lookup = {
    (r["article_type"], r["question"], r["writer_model"]): r["grounded_factual_consistency"]
    for r in grounded["results"]
}

csv_path = base / "web_eval_20260423T094539Z.csv"
rows = []
patched = 0

with open(csv_path, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        key = (row["article_type"], row["market_question"], row["writer_model"])
        if key in lookup:
            row["factual_consistency"] = str(lookup[key])
            criteria = ["grammar", "factual_consistency", "clarity", "relevance", "format"]
            row["total"] = str(sum(int(row[c]) for c in criteria))
            patched += 1
        rows.append(row)

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Patched {patched}/{len(rows)} rows. {len(rows) - patched} rows kept original score (no grounded entry).")
