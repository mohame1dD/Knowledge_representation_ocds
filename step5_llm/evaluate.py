"""Step 5d: score the text-to-SPARQL layer on the test set.

    python step5_llm/evaluate.py

For an answerable question, the system is right if its result rows equal the
gold query's rows (compared as sets of value tuples, column names ignored).
For an unanswerable one, it is right if it refuses. Output: output/step5/evaluation.md
In replay mode this tests the PIPELINE (checks, repairs, refusals), not a model.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ask import ask, check, model  # noqa: E402
from common.config import LLM_MODE, OUT  # noqa: E402
from common.sparql import select  # noqa: E402

DEST = OUT / "step5"
DEST.mkdir(parents=True, exist_ok=True)
tests = [json.loads(l) for l in (Path(__file__).resolve().parent / "tests.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
llm = model()


def as_set(cols, rows):
    out = set()
    for r in rows:
        vals = []
        for c in cols:
            v = r.get(c)
            try:
                v = round(float(v), 4)
            except (TypeError, ValueError):
                pass
            vals.append(v)
        out.add(tuple(vals))
    return out


lines, ok_a, n_a, ok_r, n_r, repairs = [], 0, 0, 0, 0, 0
for t in tests:
    r = ask(t["question"], llm, verbose=False)
    if r["status"] == "error":                 # the model never answered: a failure, but keep going
        n_a += t["expect"] == "answer"
        n_r += t["expect"] == "refuse"
        lines.append(f"| ✗ | {t['expect']} | {t['question']} | {r['reason'][:70]} | |")
        print(lines[-1], flush=True)
        continue
    if t["expect"] == "answer":
        n_a += 1
        # compare like with like: the gold query gets the same safety cap (LIMIT 100) that
        # ask.py adds to list queries, otherwise a long list can never match
        gold_q, _ = check(t["gold"])
        gc, gr = select(gold_q or t["gold"])
        good = r["status"] == "answered" and as_set(r["columns"], r["rows"]) == as_set(gc, gr)
        ok_a += good
        repairs += r.get("repairs", 0)
        note = f"{len(r.get('rows', []))} rows, {r.get('repairs', 0)} repairs" if r["status"] == "answered" else "refused"
    else:
        n_r += 1
        good = r["status"] == "refused"
        ok_r += good
        note = r.get("reason", "")[:70] if good else "ANSWERED (should refuse)"
    errs = [x["error"][:60] for x in r["trace"] if "error" in x]
    lines.append(f"| {'✓' if good else '✗'} | {t['expect']} | {t['question']} | {note} | {'; '.join(errs)} |")
    print(lines[-1], flush=True)

md = [f"# Step 5: text-to-SPARQL evaluation (LLM_MODE={LLM_MODE})", "",
      f"Answerable: {ok_a}/{n_a} correct (execution match with the gold query), {repairs} repairs used.",
      f"Unanswerable: {ok_r}/{n_r} correctly refused.", ""]
if LLM_MODE == "replay":
    md += ["**Replay mode:** the 'model' is a hand-written fixture (step5_llm/replay.json) with three "
           "deliberately wrong first attempts and one DELETE. These numbers show the checks, repair loop and "
           "refusals work. They are not a model's accuracy: run with LLM_MODE=anthropic or gemini for that.", ""]
md += ["| | Expect | Question | Result | Errors caught |", "|---|---|---|---|---|"] + lines
(DEST / "evaluation.md").write_text("\n".join(md) + "\n", encoding="utf-8")
print("\n".join(md[:4]))
