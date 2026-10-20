"""Step 5c: ask the graph in English. LLM writes SPARQL; we check it, run it, repair it, or refuse.

    python step5_llm/ask.py "How many contracts were terminated?"

Pipeline (the Session 7 lab's design)
  1. generate  : the LLM gets the schema (built from void.ttl), the 3 worked examples from
                 examples.ttl that share the most words with the question, and the question.
                 It returns SPARQL, or "REFUSE: reason"
  2. check     : parses? read-only SELECT/ASK? every ppo: class and property really occurs
                 in the graph, i.e. in void.ttl? LIMIT added if missing
  3. run       : on Fuseki (FUSEKI_URL) or the local graph
  4. repair    : any failure goes back to the LLM with the error, at most 2 times
  5. refuse    : if the LLM refuses, or still fails after the repairs
LLM_MODE in .env: replay (offline fixture), anthropic, or gemini.
"""
import json
import re
import sys
import time
from pathlib import Path

import rdflib
import requests
from rdflib.plugins.sparql import prepareQuery

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import config as C  # noqa: E402
from common.sparql import select  # noqa: E402

HERE = Path(__file__).resolve().parent
MAX_REPAIRS = 2
VOID = rdflib.Namespace("http://rdfs.org/ns/void#")
SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")

_void_file = C.OUT / "step5" / "void.ttl"
if not _void_file.exists():
    raise SystemExit("Run step5_llm/make_void.py and step5_llm/schema_card.py first")
_v = rdflib.Graph().parse(_void_file, format="turtle")
VOID_CLASSES = {str(o)[len(C.PPO):] for o in _v.objects(None, VOID["class"]) if str(o).startswith(C.PPO)}
VOID_PROPS = {str(o)[len(C.PPO):] for o in _v.objects(None, VOID.property) if str(o).startswith(C.PPO)}
_card = C.OUT / "step5" / "schema_card.md"          # the freshest copy (shared with Docker)
CARD = (_card if _card.exists() else HERE / "schema_card.md").read_text(encoding="utf-8")

_ex = rdflib.Graph().parse(HERE / "examples.ttl", format="turtle")
EXAMPLES = [(str(_ex.value(e, rdflib.RDFS.comment)), str(_ex.value(e, SH.select)))
            for e in sorted(_ex.subjects(rdflib.RDF.type, SH.SPARQLExecutable))]
STOP = {"the", "a", "an", "of", "in", "to", "is", "are", "was", "were", "how", "many", "which", "what",
        "who", "did", "do", "does", "and", "for", "by", "on", "with", "most", "their", "there"}


def words(t):
    return {w for w in re.findall(r"[a-záéíóúñ0-9]+", t.lower()) if w not in STOP}


def pick_examples(question, k=3):
    """The k worked examples that share the most words with the question."""
    q = words(question)
    return sorted(EXAMPLES, key=lambda e: -len(q & words(e[0])))[:k]


def system_prompt(question):
    shots = "\n\n".join(f"Question: {q}\nQuery:\n{s}" for q, s in pick_examples(question))
    return f"""You translate questions about Paraguay's public procurement graph into SPARQL 1.1.
Answer with ONE read-only SELECT or ASK query and nothing else (no prose, no code fences).
Use only the classes and properties in the schema. If the question cannot be answered from this
graph (facts it does not hold, opinions, predictions, wrongdoing, contact details, or any change
to the data), answer exactly: REFUSE: <one short reason>.

{CARD}
## Worked examples
{shots}"""


# ------------------------------------------------------------------ models
class Replay:
    def __init__(self):
        self.data = json.loads((HERE / "replay.json").read_text(encoding="utf-8"))["responses"]
        self.calls = {}

    def __call__(self, question, history, system=None):
        i = self.calls.get(question, 0)
        self.calls[question] = i + 1
        seq = self.data.get(question, ["REFUSE: no recorded answer for this question in replay mode"])
        return seq[min(i, len(seq) - 1)]


class LLMError(Exception):
    """The model could not be reached or gave no usable answer, even after retries."""


RETRY_STATUS = {429, 500, 502, 503, 504}           # rate limit and temporary server errors


def post_with_retry(url, **kw):
    """POST to the model API; retry slow, dropped or rate-limited calls up to 4 times."""
    delays = [5, 15, 30]
    for attempt in range(len(delays) + 1):
        if C.LLM_DELAY:
            time.sleep(C.LLM_DELAY)                 # stay under the free tier's requests per minute
        try:
            r = requests.post(url, timeout=180, **kw)
            if r.status_code in RETRY_STATUS and attempt < len(delays):
                wait = int(r.headers.get("Retry-After") or delays[attempt])
                print(f"  model busy (HTTP {r.status_code}), retrying in {wait}s", flush=True)
                time.sleep(wait)
                continue
            if r.status_code >= 400:
                raise LLMError(f"HTTP {r.status_code}: {r.text[:200]}")
            return r.json()
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt == len(delays):
                raise LLMError(f"no answer after {attempt + 1} tries: {type(e).__name__}") from e
            print(f"  model slow or unreachable ({type(e).__name__}), retrying in {delays[attempt]}s", flush=True)
            time.sleep(delays[attempt])
    raise LLMError("no answer after retries")


def anthropic(question, history, system):
    msgs = [{"role": "user", "content": question}] + history
    js = post_with_retry("https://api.anthropic.com/v1/messages", headers={
        "x-api-key": C.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": C.ANTHROPIC_MODEL, "max_tokens": 1000, "system": system, "messages": msgs})
    return "".join(b.get("text", "") for b in js.get("content", []))


def gemini(question, history, system):
    turns = [{"role": "user", "parts": [{"text": question}]}] + [
        {"role": "model" if h["role"] == "assistant" else "user", "parts": [{"text": h["content"]}]} for h in history]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{C.GEMINI_MODEL}:generateContent"
    js = post_with_retry(url, params={"key": C.GEMINI_API_KEY},
                         json={"systemInstruction": {"parts": [{"text": system}]}, "contents": turns})
    cands = js.get("candidates") or []
    if not cands:
        raise LLMError(f"no answer from Gemini: {str(js.get('promptFeedback', js))[:200]}")
    parts = cands[0].get("content", {}).get("parts", [])
    # newer models may send "thought" parts first: keep only the answer text
    return "".join(x.get("text", "") for x in parts if not x.get("thought"))


def model():
    if C.LLM_MODE == "anthropic":
        if not C.ANTHROPIC_API_KEY:
            raise SystemExit("Set ANTHROPIC_API_KEY in .env")
        return anthropic
    if C.LLM_MODE == "gemini":
        if not C.GEMINI_API_KEY:
            raise SystemExit("Set GEMINI_API_KEY in .env")
        return gemini
    return Replay()


# ------------------------------------------------------------------ checks
def clean(text):
    t = text.strip()
    t = re.sub(r"^```(?:sparql)?\s*|\s*```$", "", t, flags=re.I)
    return t.strip()


def check(q):
    """Return (query to run, None) or (None, error message for the repair prompt)."""
    head = re.sub(r"PREFIX\s+\S+\s*<[^>]*>", "", q, flags=re.I).strip().upper()
    if not (head.startswith("SELECT") or head.startswith("ASK")):
        return None, "Only read-only SELECT or ASK queries are allowed."
    try:
        prepareQuery(q)
    except Exception as e:
        return None, f"SPARQL syntax error: {e}"
    # every term must really occur in the graph: check against void.ttl, not the ontology
    used = set(re.findall(r"ppo:([A-Za-z_][A-Za-z0-9_]*)", q))
    problems = []
    for t in sorted(used):
        if t[0].isupper() and t not in VOID_CLASSES:
            problems.append(f"ppo:{t} is not a class of this graph. The classes are: "
                            + ", ".join("ppo:" + c for c in sorted(VOID_CLASSES)) + ".")
        elif t[0].islower() and t not in VOID_PROPS:
            problems.append(f"ppo:{t} is not a property of this graph. The properties are: "
                            + ", ".join("ppo:" + p for p in sorted(VOID_PROPS)) + ".")
    if problems:
        return None, " ".join(problems)
    if head.startswith("SELECT") and not re.search(r"\bLIMIT\s+\d+", q, re.I) and "COUNT(" not in q.upper() \
            and "AVG(" not in q.upper():
        q += "\nLIMIT 100"
    return q, None


def ask(question, llm=None, verbose=True):
    llm = llm or model()
    system = system_prompt(question)
    history, trace = [], []
    for attempt in range(MAX_REPAIRS + 1):
        try:
            out = clean(llm(question, history, system))
        except LLMError as e:
            trace.append({"attempt": attempt, "error": f"LLM error: {e}"})
            return {"question": question, "status": "error", "reason": f"the model did not answer ({e})",
                    "trace": trace}
        if out.upper().startswith("REFUSE"):
            trace.append({"attempt": attempt, "refused": out})
            return {"question": question, "status": "refused", "reason": out[6:].lstrip(": "), "trace": trace}
        q, err = check(out)
        if not err:
            try:
                cols, rows = select(q)
                trace.append({"attempt": attempt, "query": q, "rows": len(rows)})
                return {"question": question, "status": "answered", "query": q, "columns": cols,
                        "rows": rows, "repairs": attempt, "trace": trace}
            except Exception as e:
                err = f"Query failed when run: {e}"
        trace.append({"attempt": attempt, "query": out, "error": err})
        if verbose:
            print(f"  attempt {attempt}: {err}")
        history += [{"role": "assistant", "content": out},
                    {"role": "user", "content": f"That query was rejected: {err}\nReturn a corrected query only."}]
    return {"question": question, "status": "refused", "reason": "could not produce a valid query",
            "trace": trace}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python step5_llm/ask.py "your question"\n'
                         '       python step5_llm/ask.py --prompt "your question"   (show what the LLM receives)')
    if sys.argv[1] == "--prompt":
        print(system_prompt(" ".join(sys.argv[2:])))
        raise SystemExit
    r = ask(" ".join(sys.argv[1:]))
    if r["status"] == "refused":
        print("REFUSED:", r["reason"])
    else:
        print(r["query"], "\n")
        for row in r["rows"][:20]:
            print("  ", row)
        print(f"({len(r['rows'])} rows, {r['repairs']} repairs)")
