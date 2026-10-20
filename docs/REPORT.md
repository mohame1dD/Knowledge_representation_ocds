# Paraguay public procurement as a knowledge graph

Knowledge Representation team project. Topic: public procurement. Data: Paraguay DNCP, OCDS format.

> **Which numbers are these?** The numbers below come from the scripts in this repository run on the
> **2021 bundle** (9,276 processes); each names the file it comes from. The project is configured for
> **2019 to 2022** (`YEARS` in `.env`). `python run_all.py` (or `docker compose up --build`) regenerates
> every file in `output/`; update the numbers here from those files.

The flow: **1** data and profiling, **2** R2RML mapping to RDF, **3** ontology, **4** checking with SPARQL
and SHACL, **5** the LLM layer. All five run in Docker with one command.

## 1. Data and profiling

Source: OCP Data Registry, publication 63 (Paraguay DNCP), CSV bundles per year. Licence CC BY 4.0,
credited in `data/LICENCE.txt` and `output/provenance.ttl`. We keep 9 of the 70+ tables.

**Finding that shaped the project:** the yearly bundles are split by a process's *last update*, not its
tender date. The 2021 bundle holds tenders published as early as 2010. So `ppo:bundleYear` carries a
warning in the ontology, and any per-year count is a lower bound (a 2021 tender last updated in 2023 is
not in our files).

Grain: one `main.csv` row is one procurement process (9,276 rows, 9,276 ocids). Child tables link with
`main_ocid`; child ids are only promised unique inside a process, so every join uses `(main_ocid, id)`.
See `step1_profiling/grain.txt` and `step1_profiling/profiles/*.html`.

`step1_profiling/constraint_inventory.csv` holds **23 rules**, each with broken / total per year. We carry
**6** through the project:

| Rule | Broken / total (2021) | Kind | Lives in |
|---|---|---|---|
| 1 Contract points to a real award of the same process | 0 / 7,102 | always holds | OWL cardinality + SHACL Violation |
| 3b Every award has a supplier | 0 / 7,427 | always holds | OWL existential + SHACL Violation |
| 9 Contract signed on or after its award | 295 / 7,097 | exceptions | SHACL Warning + triage |
| 11 Total awarded at most the tender estimate | 524 / 5,314 | exceptions | SHACL Warning + triage |
| 6e "terminated" contracts sit on active awards | 3,964 / 3,965 | label vs meaning | OWL definition of ClosedContract |
| 16 One normalised supplier name, one identifier | 4 / 5,077 | identity trap | entity resolution (Step 2) |

1 and 3b always hold, so they are candidates for axioms; 9 and 11 have exceptions worth explaining; 6e
and 16 are problems of meaning and identity, not dirty data.

## 2. R2RML mapping: from the database to RDF

The transformation is declarative. `step2_mapping/load_db.py` loads the CSVs into SQLite (standing in for
DNCP's database; one line in `mapping.ini` switches to PostgreSQL) and adds **views that clean on the
way**: method labels are trimmed (rule 18), and OCDS status codes become PPO class IRIs (`"terminated"`
becomes `ppo:ClosedContract`, rule 6e). `mapping.r2rml.ttl` (W3C R2RML) says how each view becomes triples;
**Morph-KGC** runs it. `run_mapping.py` writes the result as Turtle with prefixes and grouping:
**318,730 triples**, in chunks of 2,000 whole processes (`output/graph/chunks/`), plus the shared
organisations and methods, glued into `output/graph/graph.ttl`. No hand-written converter is involved.

IRI scheme: `process/{ocid}`, `tender/{ocid}`, `award/{ocid}/{id}`, `contract/{ocid}/{id}`, `org/{party id}`,
`method/{slug}` under `https://ul.edu.lb/kr/id/py/`. Built from the source's own identifiers, so a rebuild
gives the same names, and an organisation keeps one IRI across every process it appears in.

**Why materialise and not virtualise (Ontop):** DNCP publishes periodic file exports, not a live database,
and SHACL, the reasoner sample and the LLM layer all need real triples.

**Entity resolution** (`entity_resolution.py`, `output/step2/er_report.txt`). Rule 16 led to a bigger problem:
**2,289 parties are notified suppliers with a hashed, per-process id and no identifier.**

| Case | Example | Decision | 2021 |
|---|---|---|---|
| Same RUC except the check digit, same name | 3564077 / 3564077-4 | `owl:sameAs` | 1 |
| Same number, different names | 80044691 CONSORCIO NUTRISA / 80044691-7 BELTROM SA | not merged | 1 |
| Same name, different numbers | MIGUEL ACOSTA BENITEZ, two RUCs | never merged, flagged | 71 |
| Hashed notified supplier, name only | | `ppo:candidateSameAs` if exactly one match | 419 of 2,289 |

The weaker `ppo:candidateSameAs` is on purpose: `owl:sameAs` merges two individuals, so a wrong guess would
copy one company's contracts onto another. In 109 cases the same process also lists an identified
organisation with that name, and the rule picked it every time. This is a consistency check, not a
hand-labelled gold set, since it also matches on name.

## 3. Ontology (PPO 1.1.0)

`step3_ontology/ppo.ttl`. Six core classes (ProcurementProcess, Tender, Award, Contract, Organization,
ProcurementMethod), three defined role classes (Buyer, Supplier, Tenderer), and status classes defined by
their OCDS code. Every class traces to a competency question (in the ontology header).

**Reuse.** We align to the TBFY OCDS ontology (mirrors OCDS, inactive since about 2020) and to ePO 5.2.0 (EU,
October 2025) with `rdfs:subClassOf`, without importing: ePO core alone has 150 classes. `reason.py` checks
all 14 aligned terms exist in the copies in `external/`. **`ppo:Tender` is deliberately not aligned to
`epo:Tender`:** in ePO a Tender is a company's offer, in OCDS the buyer's call for offers.

**Profile.** OWL 2 DL, checked with HermiT: the qualified cardinality on Contract (exactly one Award) and the
negated existentials (a PlanningTender has no award) are outside OWL 2 EL.

**What the reasoner did** (`output/step3/reasoner_report.txt`):
- Caught a bug in our first version: `xsd:gYear` is not in the OWL 2 datatype map (fixed in 1.0.1).
- On 300 processes with the stored status classes *removed*, it re-inferred them from the codes (181
  ClosedContract, 246 CompleteTender) and inferred 103 buyers, 348 suppliers, 578 tenderers.
- A planted UnsuccessfulTender with an award makes the ontology **inconsistent** (rule 6c), as designed.
- A contract with two different awards is **not** an error to OWL: the functional property makes it conclude
  the two awards are the same, until we add "a1 differentFrom a2". Open world and no unique name
  assumption: this is why rule 1 also needs SHACL.
- Scale: 300 processes take about 2 minutes; 1,500 did not finish in 7. The reasoner checks the model on a
  sample, SHACL checks all the data.

`tools/make_protege_file.py` writes `output/protege/ppo_with_sample.ttl` (the ontology + 25 whole
processes) to open in Protégé and reason on by hand.

## 4. Checking: SPARQL and SHACL

**SPARQL competency queries** (`step4_checking/queries/`, results `output/step4/queries/`). Eight queries,
one per competency question. Two findings came from them: some estimates are placeholders (1, 2 or 57
PYG), and PETROPAR's top suppliers are international fuel traders.

**SHACL** (`step4_checking/shapes.ttl`), validated chunk by chunk (every selected rule lives inside one
process, so this equals validating the whole graph). **Violations: 0. Warnings: 819** (= 524 rule 11 +
295 rule 9, matching Step 1 exactly). Triage (`output/step4/triage_summary.md`):

| Rule | Category | Decision | Count |
|---|---|---|---|
| 9 | same day (dateSigned stored at 12:00) | accept | 20 |
| 9 | signed within a month before award | review | 156 |
| 9 | more than a month before | flag: probable data error | 119 |
| 11 | placeholder estimate under 1,000 PYG | data error | 4 |
| 11 | overrun at most 10% | accept | 350 |
| 11 | overrun 10 to 50% | review | 139 |
| 11 | overrun over 50% | flag | 31 |

**OWL or SHACL per rule:** what must hold by *meaning* is an axiom; what we must *check in the data* is a
shape. Rules 9 and 11 compare dates and sum money, which OWL cannot do, and their exceptions are real, so
they are Warnings that never block. **Lesson:** `sh:severity` on a SPARQL constraint is ignored; severity
belongs to the shape. Our first run reported every rule 9 and 11 result as a Violation.

**The gate** (`tools/gate.py`) fails on any new Violation and runs before anything reaches Fuseki: in
`run_all.py`, in the Docker pipeline, in the git pre-commit hook and on GitHub. A violation inspected and
accepted as DNCP's own data error is listed with a reason in `step4_checking/known_issues.csv`; the gate
prints every accepted one. `tools/gate_demo.py` removes one `basedOnAward` and one `awardedTo`: the gate
reports rules 1 and 3b and blocks. **Provenance:** `output/provenance.ttl` (PROV-O) records the source and
licence, every input CSV with SHA-256, the mapping used, the build time and commit, and the PPO version IRI
the graph conforms to.

## 5. The LLM layer

Following the Session 7 lab. `make_void.py` describes what is **actually in** the graph as VoID
(`output/step5/void.ttl`: a count per class and every property from class to class, in SIB's
void-generator layout). `schema_card.py` turns it into one line per class and per property. We use VoID
rather than the ontology because the ontology says what could be true while VoID says what is there:
`ppo:Supplier` is an ontology class with no stored instances, since it is inferred.

`ask.py` gives the LLM that schema plus the 3 worked examples from `examples.ttl` (stored as
`sh:SPARQLExecutable`) that share the most words with the question. Every query is checked before it runs:
read only, parses, every `ppo:` class and property occurs in `void.ttl` (the error lists the real ones),
`LIMIT` added to long lists. Any error goes back to the model for up to 2 repairs; then it refuses.
`serve.py` exposes it with the TEXT2SPARQL contract (`GET /?question=...&dataset=...` returns the query).

Test set (`tests.jsonl`): 11 answerable questions with gold queries, 4 that must be refused (bribery, the
future, a delete, contact details). `output/step5/evaluation.md`, **replay mode**: 11/11 answered with 3
repairs, 4/4 refused. The replay "model" is a hand-written fixture with three wrong first attempts (a
property that does not exist, a class with no instances, a syntax error) and one DELETE, so this measures
the checks and the repair loop, **not a model**. With `LLM_MODE=gemini` and a key, the same script scores
a real model. One test is a meaning trap: "How many contracts were terminated?" must count ClosedContract
and be read as *closed*, not failed.

**The 4 year data exposed an evaluation bug:** the 100 row safety cap made a correct PETROPAR answer look
wrong once it had more than 100 suppliers. We now apply the same cap to the gold query.

## 6. Deployment

`docker compose up --build` starts three containers: Fuseki, the pipeline (Steps 1 to 5, then exits) and
the access layer. Every port is bound to 127.0.0.1; the Fuseki password and the model key are read only
from `.env`; the access layer starts only if the pipeline, and so the SHACL gate, succeeded.

## 7. Open problem: time (Session 7, problem 4)

Our graph stores each contract's latest status, not when it changed. "How many contracts were active on
1 June 2021?" cannot be answered, and the bundle split by last update means a re-download can silently
move a process between years. Modelling status changes as dated events would make both visible.

## 8. What we would do differently

Model statuses as dated events instead of classes; add a small hand-labelled gold set for entity
resolution; publish `examples.ttl` on the endpoint so other tools can reuse it.
