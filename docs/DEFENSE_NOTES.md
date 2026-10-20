# Defense notes

The lecturer's scale: 0 can't explain, 1 says what it does, 2 says why, **3 defends it against an
alternative or a failure of our own**. Every answer below is written to reach 3: decision, why, the
alternative we rejected, and the evidence.

## "Why does it exist? Which competency question needs it?"

**ppo:Award** (why not link Contract straight to Organization?) CQ1 asks who won from a buyer, CQ6 who bid
but didn't win. Winning is decided at the award, before any contract: 325 awards in 2021 never became a
contract (rule 5). Without Award we would lose those winners.

**ppo:resultsInAward** (why, when the process already hasAward?) Rule 6c is about *tenders*: a planning tender
can have no award. The axiom needs a property from Tender to Award to say that.

**ppo:candidateSameAs** (why not just owl:sameAs?) owl:sameAs merges two individuals and copies every fact
across. For notified suppliers the only evidence is a name; a wrong sameAs would give one company another's
contracts. The weaker property records the guess without the damage.

**ppo:bundleYear** (why keep it if it's misleading?) It is provenance: which file a process came from. Its
scopeNote says not to use it as a date. Dropping it would hide the finding.

## "Why a mapping and not a Python converter?"

The R2RML file is declarative: it states what each column becomes, any R2RML engine can run it (Morph-KGC
here, Ontop for virtualisation), and moving to PostgreSQL is one line in `mapping.ini`. The cleaning lives in
SQL views, so the mapping itself has no logic to debug. We **materialise** instead of virtualising because DNCP
publishes file exports, not a live database, and SHACL, the reasoner and the LLM layer all need triples.

## "This rule: a SHACL shape or an OWL axiom, and why?"

| Rule | Where | Why there, not the other |
|---|---|---|
| 1 | Both | OWL says what a contract *is* (exactly one award). But the reasoner merges two awards instead of complaining (test 4b), so SHACL does the counting. |
| 3b | Both | OWL: every award has *some* supplier (open world: no error if missing). SHACL: show me one. |
| 6c | OWL only | It must hold by meaning and held 0 / 3,366. The reasoner caught our planted violation as a contradiction. |
| 6e | OWL + SHACL | A meaning problem: the definition of ClosedContract fixes how "terminated" is read. SHACL checks one status per contract. |
| 9, 11 | SHACL Warning | OWL can't compare dates or sum amounts, and their exceptions are real (295 and 524), so they must never block. |
| 6a, 6b | neither | 267 and 24 exceptions. As axioms they would make the real data inconsistent. |

## "How do you know it's right?"

- Step 4 finds exactly the warnings Step 1 counted (295 + 524) and 0 violations: two independent checks agree.
- The mapped graph has the same facts as the converter we used before switching to R2RML, except the 3 method
  labels the views trim on purpose.
- Every number traces to a file in `output/` (each one is named in `docs/REPORT.md`).
- The 4 year data found things 2021 hid: a rule 6e case and an evaluation bug (the 100 row cap). Both are fixed
  or documented, not ignored.

## "What does the system do when it doesn't know?"

It refuses. Show it live:

```bash
python step5_llm/ask.py "Who bribed officials to win contracts?"     # REFUSED, with a reason
python step5_llm/ask.py "Delete all contracts from the graph."       # read-only guard
python step5_llm/ask.py "How many contracts were terminated?"        # answers, as ClosedContract
```

Three layers: the LLM refuses what the graph doesn't hold; the checks reject a query whose terms don't occur in
the graph (checked against the VoID, not the ontology); after 2 failed repairs it gives up instead of guessing.

**"Why VoID and not the ontology?"** The ontology says what could be true, VoID what is there, with counts.
ppo:Supplier exists in the ontology but has zero stored instances, so a query using it returns nothing: the VoID
check rejects it and tells the model the real classes.

**"Your score is 11/11. Really?"** In replay mode, yes, because we wrote the answers. Say it first: replay tests the
checks and the repair loop (3 planted mistakes caught and repaired, 1 DELETE blocked). With `LLM_MODE=gemini` the
same script scores a real model.

## The Session 8 deployment checklist

| Item | How we meet it |
|---|---|
| One command starts the stack from a clean checkout | `docker compose up --build` (after copying `.env.example` to `.env`) |
| Every service on 127.0.0.1 only; keys only in `.env` | ports `127.0.0.1:3030` and `127.0.0.1:8000`; Fuseki password and LLM key read from `.env` |
| The SHACL gate runs before data reaches the endpoint | `run_all.py` runs `tools/gate.py` before `load_fuseki.py`; `access` waits for the pipeline to succeed |
| The test set's score is recorded | `output/step5/evaluation.md`, with `LLM_MODE` in its title |
| An unanswerable question is refused, with a reason | `/?question=Who bribed officials?` returns `"status": "refused"` and the reason |

## Failures of our own (good answers for a 3)

1. **gYear:** HermiT rejected our ontology. A valid RDF datatype is not always a valid OWL 2 datatype. Fixed in 1.0.1.
2. **Severity on SPARQL constraints is ignored:** our first SHACL run reported 293 warnings as violations. Fixed by
   giving rules 9 and 11 their own Warning shapes.
3. **The validator missed what the reasoner caught:** a contract coded "terminated" but typed Active passes our
   shapes; the reasoner's definition of ClosedContract would flag it.
4. **The 100 row cap:** with 4 years, a correct PETROPAR answer looked wrong. The fix was in the comparison, not the answer.
5. **Rule 16 was too small:** the real identity problem was 2,289 notified suppliers with random ids.

## Which box was hardest, and what we'd change

Entity resolution: there's no ground truth, so every decision is a policy, not a measurement. We'd add a small
hand-labelled sample. And we'd model status changes as dated events, so "what was active on date X" becomes
answerable (open problem 4, time).
