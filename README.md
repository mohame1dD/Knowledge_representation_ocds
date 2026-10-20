# KR project: Paraguay public procurement knowledge graph

Paraguay's DNCP procurement data (OCDS) turned into a knowledge graph with a declarative
R2RML mapping, given meaning by an OWL ontology, checked with SPARQL and SHACL, and
queried in plain English through an LLM that is checked at every step.

- **What it all means, in plain words:** `docs/EXPLAINED.md`
- **Results and decisions:** `docs/REPORT.md`
- **Defense prep:** `docs/DEFENSE_NOTES.md`

## The flow

| Step | Folder | What it does | Tools |
|---|---|---|---|
| 1 Data + profiling | `data/`, `step1_profiling/` | download 4 years, profile the tables, check 23 business rules | pandas, ydata-profiling |
| 2 R2RML mapping | `step2_mapping/` | CSVs → SQLite → **RDF via R2RML** → Turtle; entity resolution | SQLite, R2RML, Morph-KGC |
| 3 Ontology | `step3_ontology/` | PPO in OWL, checked by a reasoner; a file for Protégé | OWL 2, HermiT |
| 4 Checking | `step4_checking/` | SHACL validation + triage + gate, provenance, SPARQL competency queries | SHACL (pyshacl), SPARQL, PROV-O |
| 5 LLM | `step5_llm/` | VoID, schema, examples; English → checked SPARQL → answer or refusal | VoID, Gemini / Claude / replay |

## Option A: everything in Docker (one command)

Needs Docker Desktop running.

```bash
cp .env.example .env        # Windows: copy .env.example .env
# edit .env: set FUSEKI_ADMIN_PASSWORD, and for a real model LLM_MODE + its key
docker compose up --build
```

| Container | Does | Address |
|---|---|---|
| `fuseki` | the SPARQL endpoint | http://127.0.0.1:3030 (user `admin`, your password) |
| `pipeline` | Steps 1 to 5 (`run_all.py`), then exits. The SHACL gate runs before Fuseki is loaded | |
| `access` | question in, SPARQL out (TEXT2SPARQL contract) | http://127.0.0.1:8000/?question=How many contracts were terminated? |

* Every port is bound to **127.0.0.1 only**; secrets live **only in `.env`**.
* On a new SHACL violation the pipeline stops and `access` never starts. A violation we inspected and
  accepted as DNCP's own data error goes, with a reason, in `step4_checking/known_issues.csv`; then run
  `docker compose up --build` again.
* `data/`, `output/` and `step1_profiling/` are shared with your folder, so downloaded years are kept.
* Stop with Ctrl+C or `docker compose down` (add `-v` to also delete Fuseki's data).

## Option B: on your machine

Needs Python 3.11+ and Java 11+ (for the reasoner).

```bash
./setup.sh                    # Windows PowerShell: .\setup.ps1
source .venv/bin/activate     # Windows cmd: .venv\Scripts\activate.bat
python run_all.py             # all steps, in order
python run_all.py --from 3    # restart from a step
```

Or one script at a time, in this order:

```bash
python data/fetch_data.py                 # 1  data
python step1_profiling/profiling.py       # 1  profiles/*.html, grain.txt
python step1_profiling/rule_checks.py     # 1  constraint_inventory.csv
python step2_mapping/load_db.py           # 2  data/procurement.db
python step2_mapping/run_mapping.py       # 2  output/graph/*.ttl
python step2_mapping/entity_resolution.py # 2  output/graph/sameas.ttl
python step3_ontology/reason.py           # 3  output/step3/reasoner_report.txt
python tools/make_protege_file.py         # 3  output/protege/ppo_with_sample.ttl
python step4_checking/validate.py         # 4  output/step4/triage.csv
python tools/gate.py --results            # 4  pass or fail
python step4_checking/provenance.py       # 4  output/provenance.ttl
python step4_checking/run_queries.py      # 4  output/step4/queries/*.csv
python step5_llm/make_void.py             # 5  output/step5/void.ttl
python step5_llm/schema_card.py           # 5  step5_llm/schema_card.md
python step5_llm/evaluate.py              # 5  output/step5/evaluation.md
python step5_llm/ask.py "How many contracts were terminated?"
python step5_llm/serve.py                 # 5  http://127.0.0.1:8000/?question=...
```

## Settings (`.env`)

| Setting | Default | What it does |
|---|---|---|
| `YEARS` | 2019,2020,2021,2022 | which yearly bundles to download and use |
| `SHACL_BATCH` | 2000 | processes per Turtle chunk (SHACL validates chunk by chunk) |
| `REASONER_SAMPLE` | 300 | processes given to HermiT (it is slow on more) |
| `FUSEKI_URL` | (empty) | SPARQL endpoint; empty = query the local `graph.ttl` |
| `FUSEKI_ADMIN_PASSWORD` | change-me | Fuseki's password, read by the container and the loader |
| `LLM_MODE` | replay | `replay` (offline, hand-written answers), `gemini` or `anthropic` |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | , gemini-flash-latest | key from https://aistudio.google.com/app/apikey |

## Protégé

* `step3_ontology/ppo.ttl`: the ontology (classes, properties, OntoGraf diagram)
* `output/protege/ppo_with_sample.ttl`: the ontology + 25 real processes. Reasoner → HermiT → Start
  reasoner, then click an organisation: Supplier / Buyer / Tenderer appear in yellow, inferred.

## Quality gate

```bash
git init && python tools/install_hook.py   # every commit rebuilds the graph and runs SHACL
python tools/gate_demo.py                  # shows the gate blocking two planted errors
```

The same gate runs on GitHub (`.github/workflows/gate.yml`) and inside `run_all.py`.

## Data licence

Paraguay DNCP via the OCP Data Registry (publication 63), CC BY 4.0. See `data/LICENCE.txt`.
