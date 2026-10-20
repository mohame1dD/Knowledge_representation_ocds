"""Step 2b: transform the database into RDF with the R2RML mapping, and save it as Turtle.

    python step2_mapping/load_db.py       # CSVs -> data/procurement.db (tables + cleaning views)
    python step2_mapping/run_mapping.py   # database -> RDF -> output/graph/*.ttl

The transformation is declarative: mapping.r2rml.ttl (W3C R2RML) says how each database view
becomes triples, and Morph-KGC runs it. No hand-written converter, no rdflib.

Output (Turtle):
    output/graph/chunks/part-0001.ttl ...  SHACL_BATCH whole processes per file (Step 4 validates
                                           file by file; every organisation a chunk mentions is
                                           typed in it, so each file can be checked on its own)
    output/graph/shared.ttl                organisations and procurement methods (described once)
    output/graph/graph.ttl                 everything, for Fuseki and SPARQL

How: Morph-KGC returns the triples in an Oxigraph store (pyoxigraph, which comes with it).
We group them by subject and write Turtle ourselves: @prefix lines, `a` for rdf:type,
`;` between facts about one subject, `,` between values of one property, `.` to close.
"""
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import ID, OUT, PPO, ROOT, SHACL_BATCH  # noqa: E402

RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
PREFIXES = {"ppo": PPO, "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "skos": "http://www.w3.org/2004/02/skos/core#", "xsd": "http://www.w3.org/2001/XMLSchema#"}
XSD_STRING = PREFIXES["xsd"] + "string"
HEADER = "".join(f"@prefix {p}: <{ns}> .\n" for p, ns in PREFIXES.items()) + "\n"
OCID = re.compile(rf"^{re.escape(ID)}(?:process|tender|award|contract)/([^/]+)")


# ------------------------------------------------------------------ Turtle writing
def iri(v):
    for p, ns in PREFIXES.items():             # short form only where Turtle allows it (no '/')
        if v.startswith(ns) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_\-]*", v[len(ns):]):
            return f"{p}:{v[len(ns):]}"
    return f"<{v}>"


def lit(t):
    s = t.value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
    if t.language:
        return f'"{s}"@{t.language}'
    dt = t.datatype.value if t.datatype else XSD_STRING
    return f'"{s}"' if dt == XSD_STRING else f'"{s}"^^{iri(dt)}'


def term(t):
    return lit(t) if type(t).__name__ == "Literal" else iri(t.value)


def write_turtle(path, subjects):
    """subjects: {subject IRI: {predicate IRI: set of objects as Turtle text}}"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(HEADER)
        for s in sorted(subjects):
            preds = subjects[s]
            parts = []
            if RDF_TYPE in preds:                      # types first, written as "a"
                parts.append("a " + ", ".join(sorted(preds[RDF_TYPE])))
            parts += [f"{iri(p)} {', '.join(sorted(o))}" for p, o in sorted(preds.items()) if p != RDF_TYPE]
            f.write(f"{iri(s)} " + " ;\n    ".join(parts) + " .\n\n")
    return sum(len(o) for preds in subjects.values() for o in preds.values())


# ------------------------------------------------------------------ run the mapping
try:
    import morph_kgc
except ImportError:
    raise SystemExit("pip install morph-kgc (see requirements.txt)")
if not (ROOT / "data" / "procurement.db").exists():
    raise SystemExit("Run step2_mapping/load_db.py first")

t0 = time.time()
os.chdir(ROOT)                                 # mapping.ini paths are relative to the repo root
print("Running Morph-KGC (R2RML)", flush=True)
store = morph_kgc.materialize_oxigraph(str(ROOT / "step2_mapping" / "mapping.ini"))
print(f"  {len(store):,} triples in {time.time() - t0:.0f}s", flush=True)

# group by subject; process-level subjects go to their process's chunk
by_process = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
shared = defaultdict(lambda: defaultdict(set))
for q in store:
    s, p = q.subject.value, q.predicate.value
    m = OCID.match(s)
    target = by_process[m.group(1)][s] if m else shared[s]
    target[p].add(term(q.object))

G = OUT / "graph"
(G / "chunks").mkdir(parents=True, exist_ok=True)
for f in (G / "chunks").glob("*"):
    f.unlink()
for old in ("graph.nt", "orgs.nt", "orgs.ttl"):          # files from older versions
    (G / old).unlink(missing_ok=True)

ORG = ID + "org/"
ocids = sorted(by_process)
n_triples, part = 0, 0
for start in range(0, len(ocids), SHACL_BATCH):
    part += 1
    chunk = {}
    for o in ocids[start:start + SHACL_BATCH]:
        chunk.update(by_process[o])
    # type every organisation the chunk links to, so SHACL's sh:class check works per file
    refs = {obj[1:-1] for preds in chunk.values() for objs in preds.values() for obj in objs
            if obj.startswith("<" + ORG)}
    for r in refs:
        chunk.setdefault(r, defaultdict(set))[RDF_TYPE].add("ppo:Organization")
    n_triples += write_turtle(G / "chunks" / f"part-{part:04d}.ttl", chunk)
n_triples += write_turtle(G / "shared.ttl", shared)

with open(G / "graph.ttl", "w", encoding="utf-8") as out:
    for f in sorted((G / "chunks").glob("*.ttl")) + [G / "shared.ttl"]:
        out.write(f.read_text(encoding="utf-8"))          # repeating @prefix lines is legal Turtle
print(f"{len(ocids):,} processes, {len(shared):,} shared subjects (organisations, methods), "
      f"{part} chunks -> {G / 'graph.ttl'} in {time.time() - t0:.0f}s")
