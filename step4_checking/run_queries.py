"""Step 4a: run the competency-question queries (SPARQL) and save their results.

    python step4_checking/run_queries.py

Uses Fuseki if FUSEKI_URL is set in .env (docker compose up -d), else the local file.
Results: output/step4/queries/<query>.csv
"""
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import OUT  # noqa: E402
from common.sparql import select  # noqa: E402

Q = Path(__file__).resolve().parent / "queries"
DEST = OUT / "step4" / "queries"
DEST.mkdir(parents=True, exist_ok=True)
top_buyer = None

for f in sorted(Q.glob("*.rq")):
    q = f.read_text(encoding="utf-8")
    if "<BUYER>" in q:
        q = q.replace("<BUYER>", f"<{top_buyer}>")
    t = time.time()
    cols, rows = select(q)
    secs = time.time() - t
    if f.stem == "q1_top_buyers" and rows:
        top_buyer = rows[0]["buyer"]
    with open(DEST / f"{f.stem}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"\n== {f.stem}: {len(rows)} rows in {secs:.1f}s")
    for r in rows[:5]:
        print("  ", {k: (v[:60] if v else v) for k, v in r.items()})
