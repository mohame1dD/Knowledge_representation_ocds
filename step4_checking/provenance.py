"""Step 4c: record where the graph came from (W3C PROV-O), with the ontology version.

    python step4_checking/provenance.py

Writes output/provenance.ttl: the source dataset and licence, each input CSV with
its SHA-256 and row count, the build activity with its time and git commit, and
the graph it generated, linked to the PPO version IRI it conforms to.
"""
import datetime as dt
import hashlib
import subprocess
import sys
from pathlib import Path

import rdflib
from rdflib.namespace import DCTERMS, PROV, RDF, RDFS, XSD

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import BASE, OUT, ROOT  # noqa: E402
from common.data import year_dirs  # noqa: E402

G = rdflib.Graph()
G.bind("prov", PROV)
G.bind("dcterms", DCTERMS)
P = rdflib.Namespace(BASE + "prov/")
G.bind("kp", P)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "not a git checkout"


onto = rdflib.Graph().parse(ROOT / "step3_ontology" / "ppo.ttl")
version = next(onto.objects(None, rdflib.OWL.versionIRI))
now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

src = rdflib.URIRef("https://data.open-contracting.org/en/publication/63")
G.add((src, RDF.type, PROV.Entity))
G.add((src, DCTERMS.title, rdflib.Literal("Paraguay DNCP OCDS data, OCP Data Registry")))
G.add((src, DCTERMS.license, rdflib.URIRef("https://creativecommons.org/licenses/by/4.0/")))
G.add((src, DCTERMS.publisher, rdflib.Literal("Direccion Nacional de Contrataciones Publicas (DNCP), Paraguay")))

team = P["team"]
G.add((team, RDF.type, PROV.Agent))
G.add((team, RDFS.label, rdflib.Literal("KR project team")))

act = P[f"build-{now}"]
G.add((act, RDF.type, PROV.Activity))
G.add((act, RDFS.label, rdflib.Literal("step2_mapping: CSV to SQLite (load_db.py), then R2RML with Morph-KGC (run_mapping.py)")))
G.add((act, PROV.used, rdflib.URIRef(BASE + "prov/mapping.r2rml.ttl")))
G.add((act, PROV.wasAssociatedWith, team))
G.add((act, PROV.endedAtTime, rdflib.Literal(now, datatype=XSD.dateTime)))
G.add((act, DCTERMS.identifier, rdflib.Literal(f"git {git_commit()}")))

for year, d in year_dirs():
    for f in sorted(d.glob("*.csv")):
        e = P[f"input/{year}/{f.name}"]
        G.add((e, RDF.type, PROV.Entity))
        G.add((e, PROV.wasDerivedFrom, src))
        G.add((e, DCTERMS.identifier, rdflib.Literal(f"sha256:{sha256(f)}")))
        with open(f, "rb") as fh:
            rows = sum(1 for _ in fh) - 1
        G.add((e, RDFS.comment, rdflib.Literal(f"{rows} lines, bundle year {year}")))
        G.add((act, PROV.used, e))

graph_file = OUT / "graph" / "graph.ttl"
out = P["graph"]
G.add((out, RDF.type, PROV.Entity))
G.add((out, PROV.wasGeneratedBy, act))
G.add((out, PROV.wasAttributedTo, team))
G.add((out, DCTERMS.conformsTo, version))
if graph_file.exists():
    G.add((out, DCTERMS.identifier, rdflib.Literal(f"sha256:{sha256(graph_file)}")))
G.serialize(OUT / "provenance.ttl", format="turtle")
print(f"Wrote {OUT / 'provenance.ttl'} ({len(G)} triples), graph conforms to {version}")
