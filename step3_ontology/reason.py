"""Step 3: check the ontology with a reasoner (HermiT, via owlready2; needs Java).

    python step3_ontology/reason.py

1. Alignment check: every TBFY / ePO term we point at exists in external/.
2. Ontology alone: consistent? what does HermiT infer about the classes?
3. Ontology + a sample of real data (REASONER_SAMPLE processes):
   consistent? how many buyers / suppliers / tenderers / closed contracts does it infer?
4. Two planted mistakes, to show what OWL does with bad data:
   a) an UnsuccessfulTender that results in an award  -> contradiction (inconsistent)
   b) a contract based on two different awards        -> NO error: OWL merges the awards
      (no unique name assumption). That is why step 4 needs SHACL.
Writes output/step3/reasoner_report.txt
"""
import random
import time
import sys
import tempfile
from pathlib import Path

import rdflib
from rdflib.namespace import OWL, RDF

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import OUT, PPO, REASONER_SAMPLE  # noqa: E402

HERE = Path(__file__).resolve().parent
DEST = OUT / "step3"
DEST.mkdir(parents=True, exist_ok=True)
log = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    log.append(s)


# ------------------------------------------------------------- 1. alignments
onto_g = rdflib.Graph().parse(HERE / "ppo.ttl")
ext = rdflib.Graph()
for f in (HERE / "external").glob("*.ttl"):
    ext.parse(f)
external_used = {o for o in onto_g.objects() if isinstance(o, rdflib.URIRef)
                 and str(o).startswith(("http://data.tbfy.eu/", "http://data.europa.eu/a4g/", "http://www.w3.org/ns/org#"))}
missing = [str(t) for t in external_used if (t, None, None) not in ext]
say(f"1. Alignment check: {len(external_used)} external terms used, missing from external/: {missing or 'none'}")

# --------------------------------------------------------------- owlready2
try:
    import owlready2 as o2
except ImportError:
    raise SystemExit("pip install owlready2 (and install Java for HermiT)")


PRE = {"http://data.tbfy.eu/ontology/ocds#": "tbfy:", "http://data.europa.eu/a4g/ontology#": "epo:",
       "http://www.w3.org/ns/org#": "org:", PPO: "ppo:", "http://www.w3.org/2002/07/owl#": "owl:"}


def short(iri):
    for k, v in PRE.items():
        if iri.startswith(k):
            return v + iri[len(k):]
    return iri


def to_nt(graph):
    # owlready2 cannot read Turtle (only RDF/XML, N-Triples, OWL/XML), so the reasoner
    # gets a temporary N-Triples copy. Our files stay Turtle.
    tmp = tempfile.NamedTemporaryFile(suffix=".nt", delete=False)
    graph.serialize(tmp.name, format="nt", encoding="utf-8")
    return tmp.name


def reason(graph, label):
    world = o2.World()
    onto = world.get_ontology("file://" + to_nt(graph)).load(format="ntriples")
    try:
        with onto:
            o2.sync_reasoner_hermit(world, infer_property_values=False, debug=0)
        return world, onto, None
    except o2.OwlReadyInconsistentOntologyError as e:
        return world, onto, e


# ------------------------------------------------------------ 2. ontology alone
world, onto, err = reason(onto_g, "ontology")
say(f"2. Ontology alone: {'INCONSISTENT ' + str(err) if err else 'consistent'}")
unsat = [str(c) for c in world.inconsistent_classes()]
say(f"   Unsatisfiable classes: {unsat or 'none'}")
for c in sorted(world.classes(), key=lambda c: c.iri):
    if c.iri.startswith(PPO):
        parents = sorted(short(p.iri) for p in c.is_a if hasattr(p, "iri"))
        say(f"   {short(c.iri):24} subClassOf {', '.join(parents)}")

# ------------------------------------------------- 3. ontology + data sample
chunk = sorted((OUT / "graph" / "chunks").glob("*.ttl"))
if not chunk:
    raise SystemExit("Run step2_mapping/run_mapping.py first")
data = rdflib.Graph()
data.parse(chunk[0], format="turtle")
procs = sorted(set(data.subjects(RDF.type, rdflib.URIRef(PPO + "ProcurementProcess"))))
random.seed(0)
keep_p = set(random.sample(procs, min(REASONER_SAMPLE, len(procs))))


def reachable(g, roots):
    seen, todo = set(), list(roots)
    while todo:
        s = todo.pop()
        if s in seen:
            continue
        seen.add(s)
        todo += [o for o in g.objects(s) if isinstance(o, rdflib.URIRef) and "/id/py/" in str(o)]
    return seen


nodes = reachable(data, keep_p)
sample = rdflib.Graph()
for s, p, o in data:
    if s in nodes:
        # drop the asserted status classes: the reasoner must infer them from the codes
        if p == RDF.type and str(o).endswith(("Tender", "Award", "Contract")) and str(o).split("#")[-1] not in ("Tender", "Award", "Contract"):
            continue
        sample.add((s, p, o))
say(f"3. Data sample: {len(keep_p)} processes, {len(sample):,} triples (asserted status classes removed)")
t0 = time.time()
world, onto, err = reason(onto_g + sample, "sample")
say(f"   HermiT time: {time.time() - t0:.0f}s")
if err:
    say("   INCONSISTENT:", err)
else:
    say("   consistent")
    for name in ("Buyer", "Supplier", "Tenderer", "ClosedContract", "ActiveContract",
                 "CompleteTender", "PlanningTender", "UnsuccessfulTender"):
        cls = world[PPO + name]
        say(f"   inferred {name:20} {len(list(cls.instances())):>6} individuals")

# ------------------------------------------------------------- 4. planted bugs
P = rdflib.Namespace(PPO)
X = rdflib.Namespace("https://ul.edu.lb/kr/id/test/")
bad = rdflib.Graph()
bad.add((X.t1, RDF.type, P.Tender))
bad.add((X.t1, P.statusCode, rdflib.Literal("unsuccessful")))
bad.add((X.a1, RDF.type, P.Award))
bad.add((X.t1, P.resultsInAward, X.a1))
_, _, err = reason(onto_g + bad, "bug a")
say(f"4a. Unsuccessful tender with an award: {'INCONSISTENT (caught, as intended)' if err else 'not caught'}")

bad = rdflib.Graph()
bad.add((X.c1, RDF.type, P.Contract))
for a in (X.a1, X.a2):
    bad.add((a, RDF.type, P.Award))
    bad.add((X.c1, P.basedOnAward, a))
_, _, err = reason(onto_g + bad, "bug b")
say(f"4b. Contract with two awards: {'INCONSISTENT' if err else 'consistent, no complaint'}")
bad.add((X.a1, OWL.differentFrom, X.a2))
_, _, err2 = reason(onto_g + bad, "bug b2")
say(f"    ... same data + 'a1 differentFrom a2': {'INCONSISTENT' if err2 else 'consistent'}")
if not err and err2:
    say("    So OWL silently concluded the two awards are the SAME award (functional property, "
        "no unique name assumption). It only complains once told they differ. SHACL (step 4) "
        "counts values and reports the second award directly.")

(DEST / "reasoner_report.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
print(f"\nReport: {DEST / 'reasoner_report.txt'}")
