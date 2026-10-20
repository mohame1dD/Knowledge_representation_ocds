"""The quality gate: exit 1 if any NEW SHACL Violation is found, so bad data is blocked.

    python tools/gate.py                 # validate every chunk of output/graph
    python tools/gate.py some_file.ttl   # validate one file (used by the demo)
    python tools/gate.py --results       # judge the report validate.py just wrote (no second
                                         # validation; run_all.py uses this)

Warnings (rules 9 and 11) never block: they are real exceptions, triaged in Step 4.

Known issues: a violation we inspected and cannot fix (it is wrong in DNCP's own data)
is listed in step4_checking/known_issues.csv with the rule and a reason. The gate accepts
exactly those focus nodes and still blocks any other violation. Every accepted one is
printed, so nothing is hidden.

Run by: the git pre-commit hook (python tools/install_hook.py), the GitHub workflow,
and run_all.py (also inside Docker) before anything is loaded into Fuseki.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "step4_checking"))
from common.config import OUT, ROOT  # noqa: E402
from validate import validate_file  # noqa: E402

KNOWN_FILE = ROOT / "step4_checking" / "known_issues.csv"


def known_issues():
    if not KNOWN_FILE.exists():
        return {}
    with open(KNOWN_FILE, encoding="utf-8") as f:
        return {r["focus"].strip(): r for r in csv.DictReader(f) if r.get("focus", "").strip()}


def run(files):
    known = known_issues()
    new, accepted = [], []
    for f in files:
        _, rows, _ = validate_file(f)
        viol = [r for r in rows if r["severity"] == "Violation"]
        for r in viol:
            (accepted if r["focus"] in known else new).append(r)
        print(f"gate: {f.name}: {len(viol)} violations, "
              f"{sum(r['severity'] == 'Warning' for r in rows)} warnings", flush=True)
    for r in accepted:
        print(f"  accepted known issue, rule {r['rule']}: {r['focus']}  ({known[r['focus']]['reason']})")
    if new:
        print(f"\nGATE FAILED: {len(new)} new violation(s). First ones:")
        for r in new[:5]:
            print(f"  rule {r['rule']}: {r['focus']}  {r['message']}")
        print(f"\nInspect them. If one is DNCP's own data error, add it to {KNOWN_FILE.name} with a reason.")
        return 1
    print(f"GATE PASSED ({len(accepted)} known issue(s) accepted)")
    return 0


def run_from_results():
    path = OUT / "step4" / "validation_results.csv"
    if not path.exists():
        raise SystemExit("No report yet: run step4_checking/validate.py first")
    known = known_issues()
    with open(path, encoding="utf-8") as f:
        viol = [r for r in csv.DictReader(f) if r["severity"] == "Violation"]
    new = [r for r in viol if r["focus"] not in known]
    for r in viol:
        if r["focus"] in known:
            print(f"  accepted known issue, rule {r['rule']}: {r['focus']}  ({known[r['focus']]['reason']})")
    if new:
        print(f"GATE FAILED: {len(new)} new violation(s). First ones:")
        for r in new[:5]:
            print(f"  rule {r['rule']}: {r['focus']}  {r['message']}")
        print(f"\nInspect them. If one is DNCP's own data error, add it to {KNOWN_FILE.name} with a reason.")
        return 1
    print(f"GATE PASSED ({len(viol) - len(new)} known issue(s) accepted)")
    return 0


if __name__ == "__main__":
    if "--results" in sys.argv:
        sys.exit(run_from_results())
    files = [Path(a) for a in sys.argv[1:]] or sorted((OUT / "graph" / "chunks").glob("*.ttl"))
    sys.exit(run(files))
