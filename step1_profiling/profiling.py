"""Step 1b: profile the DNCP OCDS tables (all configured years).

    python step1_profiling/profiling.py            # grain table + HTML reports
    python step1_profiling/profiling.py --no-html  # grain table only (fast)

First question of every profile: what does one row stand for (the grain)?
Then ydata-profiling writes one HTML report per table into step1_profiling/profiles/.
Big tables are sampled so the reports finish on a laptop.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import YEARS  # noqa: E402
from common.data import load  # noqa: E402

SAMPLE = 50_000
TABLES = ["main", "parties", "awards", "awards_suppliers", "contracts",
          "tender_tenderers", "tender_lots", "tender_items",
          "contracts_implementation_transactions"]
OUT = Path(__file__).resolve().parent / "profiles"
OUT.mkdir(exist_ok=True)

frames = {}
lines = [f"Years: {', '.join(map(str, YEARS))}", "",
         f"{'table':40} {'rows':>9} {'processes':>10} {'rows/process':>13}"]
for t in TABLES:
    try:
        df = load(t)
    except SystemExit:
        lines.append(f"{t:40} (missing)")
        continue
    frames[t] = df
    key = "ocid" if t == "main" else "main_ocid"
    n = df[key].nunique()
    lines.append(f"{t:40} {len(df):>9,} {n:>10,} {len(df) / max(n, 1):>13.2f}")

lines += ["", "Processes per year (main.csv):"]
for y, n in frames["main"].groupby("year").size().items():
    lines.append(f"  {y}: {n:,}")
report = "\n".join(lines)
print(report)
(Path(__file__).resolve().parent / "grain.txt").write_text(report + "\n")

if "--no-html" in sys.argv:
    sys.exit()
try:
    from ydata_profiling import ProfileReport
except ImportError:
    raise SystemExit("pip install ydata-profiling")

for t, df in frames.items():
    sample = df.sample(SAMPLE, random_state=0) if len(df) > SAMPLE else df
    note = f" (sample of {SAMPLE:,} from {len(df):,})" if len(df) > SAMPLE else ""
    print(f"Profiling {t}{note}")
    ProfileReport(sample, title=f"DNCP {t} {YEARS[0]}-{YEARS[-1]}{note}",
                  minimal=True, progress_bar=False).to_file(OUT / f"{t}.html")
print(f"Reports in {OUT}")
