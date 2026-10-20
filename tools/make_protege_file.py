"""Make one Turtle file to open in Protegé: the PPO ontology + a sample of real data.

    python tools/make_protege_file.py          # 25 processes
    python tools/make_protege_file.py 60       # more

Output: output/protege/ppo_with_sample.ttl

The full graph (300,000+ triples, millions with 4 years) is too big to browse in Protegé,
so this takes N whole processes (tender, awards, contracts, every organisation they
mention, with names) and puts them in the same file as the ontology.

In Protegé: File > Open, pick the file, then Reasoner > HermiT > Start reasoner.
Click any organisation under Entities > Individuals: types like Supplier and Buyer show
up in yellow. They are INFERRED by the reasoner, they are not stored in the data.
"""
import random
import sys
from pathlib import Path

import rdflib
from rdflib.namespace import RDF

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import OUT, PPO, ROOT  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 25
chunks = sorted((OUT / "graph" / "chunks").glob("*.ttl"))
if not chunks:
    raise SystemExit("Run step2_mapping/run_mapping.py first")

data = rdflib.Graph().parse(chunks[0], format="turtle")
orgs = rdflib.Graph().parse(OUT / "graph" / "shared.ttl", format="turtle")
procs = sorted(data.subjects(RDF.type, rdflib.URIRef(PPO + "ProcurementProcess")))
# prefer processes that went all the way to a contract, so the sample shows every class
full = [p for p in procs if (p, rdflib.URIRef(PPO + "hasContract"), None) in data]
random.seed(0)
pick = random.sample(full, min(N, len(full)))

seen, todo = set(), list(pick)
while todo:
    s = todo.pop()
    if s in seen:
        continue
    seen.add(s)
    todo += [o for o in data.objects(s) if isinstance(o, rdflib.URIRef) and "/id/py/" in str(o)]

out = rdflib.Graph().parse(ROOT / "step3_ontology" / "ppo.ttl", format="turtle")
before = len(out)
for s in seen:
    for t in data.triples((s, None, None)):
        out.add(t)
    for t in orgs.triples((s, None, None)):       # names and RUC numbers
        out.add(t)
links = OUT / "graph" / "sameas.ttl"
if links.exists():
    for t in rdflib.Graph().parse(links, format="turtle"):
        if t[0] in seen and t[2] in seen:
            out.add(t)

dest = OUT / "protege"
dest.mkdir(exist_ok=True)
out.bind("id", "https://ul.edu.lb/kr/id/py/")
out.serialize(dest / "ppo_with_sample.ttl", format="turtle", encoding="utf-8")
print(f"{dest / 'ppo_with_sample.ttl'}: ontology ({before} triples) + {len(pick)} processes "
      f"({len(out) - before:,} data triples, {len(seen):,} individuals)")
