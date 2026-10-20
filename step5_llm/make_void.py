"""Step 5a: describe what is actually in the graph, as VoID (Vocabulary of Interlinked Datasets).

    python step5_llm/make_void.py      -> output/step5/void.ttl

Same layout as SIB's void-generator (and the Session 7 lab's make_void.py):

    <…/void> void:classPartition <…/void/Contract-partition> .
    <…/void/Contract-partition> void:class ppo:Contract ; void:entities 7102 ;
        void:propertyPartition <…/void/Contract-basedOnAward-Award> .
    <…/void/Contract-basedOnAward-Award> void:property ppo:basedOnAward ; void:triples 7102 ;
        void:classPartition [ void:class ppo:Award ] .

Why VoID and not the ontology: the ontology says what COULD be true (ppo:Supplier is a
class there), VoID says what IS there, with counts (no ppo:Supplier: it is inferred, never
stored). The model needs the second, and ask.py checks every query against it.

Computed in one pass over the graph (fast enough for the 4-year graph on a laptop).
"""
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import rdflib
from rdflib import RDF, RDFS, XSD, Literal, Namespace, URIRef

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import BASE, FUSEKI_URL, OUT, PPO, ROOT  # noqa: E402

VOID = Namespace("http://rdfs.org/ns/void#")
VEXT = Namespace("http://ldf.fi/void-ext#")          # datatype partitions, as in SIB's generator
DCT = Namespace("http://purl.org/dc/terms/")
DS = URIRef(BASE + "id/py/void")
PART = BASE + "id/py/void/"

t0 = time.time()
graph_file = OUT / "graph" / "graph.ttl"
if not graph_file.exists():
    raise SystemExit("Run step2_mapping/run_mapping.py first")
print(f"Reading {graph_file.name}")
g = rdflib.Graph().parse(graph_file, format="turtle")

# which classes count as "base" (not a status subclass of another PPO class)
onto = rdflib.Graph().parse(ROOT / "step3_ontology" / "ppo.ttl", format="turtle")
parent = {s: o for s, o in onto.subject_objects(RDFS.subClassOf)
          if str(s).startswith(PPO) and str(o).startswith(PPO)}


def base(c):
    while c in parent:
        c = parent[c]
    return c


types = defaultdict(set)
for s, c in g.subject_objects(RDF.type):
    types[s].add(c)
entities = Counter(c for cs in types.values() for c in cs)

# property partitions: (subject class, property, target) -> number of triples
parts = Counter()
for s, p, o in g:
    if p == RDF.type:
        continue
    if isinstance(o, Literal):
        target = ("datatype", o.datatype or XSD.string)
    else:
        tgt = {base(c) for c in types.get(o, ())}
        target = ("class", sorted(tgt)[0]) if tgt else ("class", None)
    for c in types.get(s, ()):
        parts[(c, p, target)] += 1


def local(iri):
    return str(iri).rsplit("#", 1)[-1].rsplit("/", 1)[-1]


v = rdflib.Graph()
for prefix, ns in (("void", VOID), ("void-ext", VEXT), ("ppo", PPO), ("xsd", XSD), ("dcterms", DCT),
                   ("rdfs", RDFS), ("skos", "http://www.w3.org/2004/02/skos/core#")):
    v.bind(prefix, ns)
v.add((DS, RDF.type, VOID.Dataset))
v.add((DS, DCT.title, Literal("Paraguay DNCP procurement knowledge graph")))
v.add((DS, DCT.license, URIRef("https://creativecommons.org/licenses/by/4.0/")))
v.add((DS, VOID.triples, Literal(len(g))))
v.add((DS, VOID.vocabulary, URIRef(PPO)))
if FUSEKI_URL:
    v.add((DS, VOID.sparqlEndpoint, URIRef(FUSEKI_URL.rstrip("/") + "/sparql")))

for c, n in entities.items():
    cp = URIRef(PART + local(c) + "-partition")
    v.add((DS, VOID.classPartition, cp))
    v.add((cp, VOID["class"], c))
    v.add((cp, VOID.entities, Literal(n)))
for (c, p, (kind, t)), n in parts.items():
    pp = URIRef(PART + f"{local(c)}-{local(p)}-{local(t) if t else 'IRI'}")
    v.add((URIRef(PART + local(c) + "-partition"), VOID.propertyPartition, pp))
    v.add((pp, VOID.property, p))
    v.add((pp, VOID.triples, Literal(n)))
    if kind == "datatype":
        dp = rdflib.BNode()
        v.add((pp, VEXT.datatypePartition, dp))
        v.add((dp, VEXT.datatype, t))
    elif t is not None:
        tp = rdflib.BNode()
        v.add((pp, VOID.classPartition, tp))
        v.add((tp, VOID["class"], t))

dest = OUT / "step5"
dest.mkdir(parents=True, exist_ok=True)
v.serialize(dest / "void.ttl", format="turtle", encoding="utf-8")
print(f"void.ttl: {len(v):,} triples describe {len(g):,} ({len(entities)} classes, "
      f"{len({p for _, p, _ in parts})} properties) in {time.time() - t0:.0f}s")
