"""Step 5b: turn void.ttl into the plain-text schema the LLM reads (the lab's schema_text()).

    python step5_llm/schema_card.py   -> step5_llm/schema_card.md (+ a copy in output/step5/)

One line per class with its count, one line per property: from which class, to which.
Built from VoID (what IS in the graph), so it lists only terms a query can actually find.
A few hand-written rules on top state what a count cannot: which classes are subclasses,
and what the status codes mean.
"""
import sys
from collections import defaultdict
from pathlib import Path

import rdflib
from rdflib import RDFS, Namespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import OUT, PPO, ROOT  # noqa: E402

VOID = Namespace("http://rdfs.org/ns/void#")
VEXT = Namespace("http://ldf.fi/void-ext#")
PREFIX = {PPO: "ppo:", "http://www.w3.org/2001/XMLSchema#": "xsd:",
          "http://www.w3.org/2000/01/rdf-schema#": "rdfs:", "http://www.w3.org/2004/02/skos/core#": "skos:"}


def short(x):
    for k, v in PREFIX.items():
        if str(x).startswith(k):
            return v + str(x)[len(k):]
    return f"<{x}>"


void_file = OUT / "step5" / "void.ttl"
if not void_file.exists():
    raise SystemExit("Run step5_llm/make_void.py first")
v = rdflib.Graph().parse(void_file, format="turtle")
onto = rdflib.Graph().parse(ROOT / "step3_ontology" / "ppo.ttl", format="turtle")
parent = {s: o for s, o in onto.subject_objects(RDFS.subClassOf)
          if str(s).startswith(PPO) and str(o).startswith(PPO)}

classes = {}
props = defaultdict(set)                     # subject class -> {(property, target)}
for cp in v.objects(None, VOID.classPartition):
    c = v.value(cp, VOID["class"])
    n = v.value(cp, VOID.entities)
    if c is None or n is None:               # nested target partitions have no count
        continue
    classes[c] = int(n)
    for pp in v.objects(cp, VOID.propertyPartition):
        p = v.value(pp, VOID.property)
        tgt = None
        for tp in v.objects(pp, VOID.classPartition):
            tgt = v.value(tp, VOID["class"])
        for dp in v.objects(pp, VEXT.datatypePartition):
            tgt = v.value(dp, VEXT.datatype)
        props[c].add((p, tgt))

lines = ["# Schema of the graph (from void.ttl)", "",
         "PREFIX ppo: <https://ul.edu.lb/kr/ont/ppo#>  PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>",
         "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>  PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>", "",
         "## Rules",
         "- Status classes are subclasses: every ppo:ClosedContract is also a ppo:Contract, and so on (listed below).",
         "- OCDS code \"terminated\" = ppo:ClosedContract: the contract ran and closed. It does NOT mean failed.",
         "- There is no Supplier, Buyer or Tenderer class in the data. Use the links: ?award ppo:awardedTo ?org,",
         "  ?process ppo:hasBuyer ?org, ?tender ppo:hasTenderer ?org.",
         "- Names: rdfs:label on organisations, skos:prefLabel on procurement methods. Amounts come with",
         "  ppo:currency (mostly \"PYG\"). Data IRIs: https://ul.edu.lb/kr/id/py/{process|tender|award|contract|org}/...",
         "", "## Classes (how many things)"]
for c, n in sorted(classes.items(), key=lambda x: -x[1]):
    sub = f"  (a kind of {short(parent[c])})" if c in parent else ""
    lines.append(f"{short(c)} ({n:,} things){sub}")
lines += ["", "## Properties (from class, to class or datatype)"]
for c in sorted(classes, key=lambda x: short(x)):
    if c in parent:                          # subclasses have the same properties as their parent
        continue
    for p, t in sorted(props[c], key=lambda x: short(x[0])):
        lines.append(f"{short(c)} {short(p)} {short(t) if t is not None else '(an IRI)'}")

text = "\n".join(lines) + "\n"
# two copies: next to the code (to read and commit), and in output/ (shared with the Docker access container)
(Path(__file__).resolve().parent / "schema_card.md").write_text(text, encoding="utf-8")
(OUT / "step5").mkdir(parents=True, exist_ok=True)
(OUT / "step5" / "schema_card.md").write_text(text, encoding="utf-8")
print(f"schema_card.md: {len(lines)} lines, {len(chr(10).join(lines)):,} characters")
