"""Step 4b: validate the graph with SHACL, chunk by chunk, then triage.

    python step4_checking/validate.py                 # all chunks
    python step4_checking/validate.py --only part-0001.ttl
    python step4_checking/validate.py --strict        # exit 1 on any violation, like the gate

This script REPORTS: it always finishes and writes the files below, even when it finds
violations. Blocking bad data is the gate's job (tools/gate.py, run by the pre-commit hook).

Every selected rule lives inside one process, so validating 2,000 processes at a
time gives exactly the same results as validating the whole graph at once, with
a fraction of the memory. (That is a design decision, written in the report.)

Output (output/step4/):
    validation_results.csv   one row per SHACL result
    triage.csv               each result with a category and a decision
    triage_summary.md        counts per rule, severity and category
"""
import csv
import sys
import time
from collections import Counter
from pathlib import Path

import pyshacl
import rdflib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import OUT  # noqa: E402

HERE = Path(__file__).resolve().parent
DEST = OUT / "step4"
DEST.mkdir(parents=True, exist_ok=True)
SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
PPS = rdflib.Namespace("https://ul.edu.lb/kr/shapes/ppo#")

shapes = rdflib.Graph().parse(HERE / "shapes.ttl")

# rule id of each constraint: look on the property shape / SPARQL constraint itself
rule_of = {}
for node, rule in shapes.subject_objects(PPS.rule):
    rule_of[node] = str(rule)


def rule_for(source_shape, constraint):
    if source_shape in rule_of:
        return rule_of[source_shape]
    if constraint == SH.XoneConstraintComponent:
        return "6e"
    if constraint == SH.SPARQLConstraintComponent:
        return "?"
    return "-"


RESULTS_Q = """
PREFIX sh: <http://www.w3.org/ns/shacl#>
SELECT ?focus ?path ?severity ?message ?shape ?component ?value WHERE {
  ?r a sh:ValidationResult ; sh:focusNode ?focus ; sh:resultSeverity ?severity ;
     sh:sourceShape ?shape ; sh:sourceConstraintComponent ?component .
  OPTIONAL { ?r sh:resultPath ?path } OPTIONAL { ?r sh:resultMessage ?message }
  OPTIONAL { ?r sh:value ?value }
}"""


def validate_file(path):
    data = rdflib.Graph()
    data.parse(path, format="turtle")
    conforms, report, _ = pyshacl.validate(data, shacl_graph=shapes, inference="none",
                                           allow_warnings=True, abort_on_first=False)
    rows = []
    for r in report.query(RESULTS_Q):
        # SPARQL constraints: the sh:sourceShape is the node shape; find which constraint
        shape = r.shape
        comp = r.component
        rule = rule_for(shape, comp)
        if rule == "?":
            msg = str(r.message or "")
            rule = "9" if msg.startswith("Rule 9") else "11" if msg.startswith("Rule 11") else \
                   "1" if msg.startswith("Rule 1") else "?"
        rows.append({"chunk": path.name, "rule": rule, "severity": str(r.severity).split("#")[-1],
                     "focus": str(r.focus), "path": str(r.path or ""), "message": str(r.message or ""),
                     "value": str(r.value or "")})
    return conforms, rows, len(data)


def triage(row):
    """Category + decision for one result. The thresholds are written in the report."""
    rule, msg = row["rule"], row["message"]
    if row["severity"] == "Violation":
        return "data or model error", "fix before commit (gate blocks)"
    if rule == "9":
        import re
        d = re.findall(r"\d{4}-\d\d-\d\dT[\d:]+[-+]\d\d:\d\d", msg)
        if len(d) == 2:
            from datetime import datetime
            gap = (datetime.fromisoformat(d[1]) - datetime.fromisoformat(d[0])).total_seconds() / 86400
            row["gap_days"] = round(gap, 2)
            if gap < 1:
                return "same-day signing (dateSigned stored at 12:00)", "accept: not a real exception"
            if gap <= 30:
                return "signed within a month before award", "review: likely award date = publication date"
            return "signed more than a month before award", "flag: probable data error"
    if rule == "11":
        import re
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?", msg.replace("Rule 11:", ""))]
        if len(nums) >= 2:
            awarded, estimate = nums[0], nums[1]
            row["over_pct"] = round((awarded / estimate - 1) * 100, 1) if estimate else ""
            if estimate < 1000:
                return "placeholder estimate (under 1,000 PYG)", "data error: estimate unusable"
            r = awarded / estimate
            if r <= 1.10:
                return "small overrun (at most 10%)", "accept: plausible price change"
            if r <= 1.50:
                return "overrun 10 to 50%", "review"
            return "overrun over 50%", "flag: red flag for investigation"
    return "other", "review"


if __name__ == "__main__":
    files = sorted((OUT / "graph" / "chunks").glob("*.ttl"))
    if "--only" in sys.argv:
        files = [f for f in files if f.name == sys.argv[sys.argv.index("--only") + 1]]
    if not files:
        raise SystemExit("No chunks: run step2_mapping/run_mapping.py")
    all_rows, ok_all = [], True
    for f in files:
        t = time.time()
        ok, rows, n = validate_file(f)
        ok_all &= not any(r["severity"] == "Violation" for r in rows)
        all_rows += rows
        print(f"{f.name}: {n:,} triples, {len(rows)} results in {time.time() - t:.0f}s")

    fields = ["chunk", "rule", "severity", "focus", "path", "message", "value"]
    with open(DEST / "validation_results.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_rows)

    for r in all_rows:
        r["category"], r["decision"] = triage(r)
    with open(DEST / "triage.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields + ["gap_days", "over_pct", "category", "decision"],
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(all_rows)

    c = Counter((r["rule"], r["severity"], r["category"], r["decision"]) for r in all_rows)
    md = ["# SHACL triage summary", "",
          f"Chunks validated: {len(files)}. Results: {len(all_rows)}. "
          f"Violations: {sum(1 for r in all_rows if r['severity'] == 'Violation')}.", "",
          "| Rule | Severity | Category | Decision | Count |", "|---|---|---|---|---|"]
    for (rule, sev, cat, dec), n in sorted(c.items(), key=lambda x: (x[0][0], -x[1])):
        md.append(f"| {rule} | {sev} | {cat} | {dec} | {n} |")
    (DEST / "triage_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    n_viol = sum(1 for r in all_rows if r["severity"] == "Violation")
    if n_viol:
        print(f"\n{n_viol} violation(s) found. They are listed in validation_results.csv and triage.csv.")
        print("This script only REPORTS. The gate that blocks commits is tools/gate.py.")
    # --strict: behave like the gate (exit 1 on any violation)
    sys.exit(1 if ("--strict" in sys.argv and n_viol) else 0)
