"""Run the whole pipeline, in order, on the years in .env.

    python run_all.py              # everything
    python run_all.py --from 3     # start at step 3 (data and graph already there)
    python run_all.py --skip-fetch # data already downloaded

    1  data + profiling   fetch, profile, check the 23 business rules
    2  R2RML mapping      CSVs -> SQLite -> RDF (Morph-KGC) -> Turtle; entity resolution
    3  ontology           HermiT reasoner on PPO + a sample; the Protege file
    4  checking           SHACL validation + triage, the GATE, provenance, SPARQL queries
    5  LLM                VoID, schema card, evaluation of the text-to-SPARQL layer

The gate stops the run on any NEW SHACL violation, before anything is loaded into Fuseki.
Fuseki is loaded only when FUSEKI_URL is set (always the case inside Docker).
"""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from common.config import FUSEKI_URL  # noqa: E402

STEPS = [
    (1, "fetch data", ["data/fetch_data.py"]),
    (1, "profiling", ["step1_profiling/profiling.py"]),
    (1, "rule checks", ["step1_profiling/rule_checks.py"]),
    (2, "load the database", ["step2_mapping/load_db.py"]),
    (2, "R2RML mapping to RDF", ["step2_mapping/run_mapping.py"]),
    (2, "entity resolution", ["step2_mapping/entity_resolution.py"]),
    (3, "reasoner", ["step3_ontology/reason.py"]),
    (3, "Protege file (ontology + sample)", ["tools/make_protege_file.py"]),
    (4, "SHACL validation + triage", ["step4_checking/validate.py"]),
    (4, "SHACL gate (blocks new violations)", ["tools/gate.py", "--results"]),
    (4, "provenance", ["step4_checking/provenance.py"]),
    (4, "load Fuseki", ["tools/load_fuseki.py"]),
    (4, "SPARQL competency queries", ["step4_checking/run_queries.py"]),
    (5, "VoID description", ["step5_llm/make_void.py"]),
    (5, "schema card (from VoID)", ["step5_llm/schema_card.py"]),
    (5, "text-to-SPARQL evaluation", ["step5_llm/evaluate.py"]),
]
start = int(sys.argv[sys.argv.index("--from") + 1]) if "--from" in sys.argv else 1
for n, name, cmd in STEPS:
    if n < start or (name == "fetch data" and "--skip-fetch" in sys.argv):
        continue
    if name == "load Fuseki" and not FUSEKI_URL:
        print("\n----- load Fuseki: skipped (FUSEKI_URL not set; queries run on the local file)")
        continue
    print(f"\n===== step {n}: {name} =====", flush=True)
    t = time.time()
    r = subprocess.run([sys.executable, *cmd], cwd=ROOT)
    print(f"----- {name}: {'ok' if r.returncode == 0 else f'exit {r.returncode}'} in {time.time() - t:.0f}s", flush=True)
    if r.returncode != 0:
        sys.exit(f"Stopped at '{name}'. Fix it and rerun with: python run_all.py --from {n}")
print("\nAll steps done. Results are in output/, docs/REPORT.md explains them.", flush=True)
