"""Run SPARQL against Fuseki (if FUSEKI_URL is set) or the local graph file."""
from functools import lru_cache

import requests

from common.config import FUSEKI_URL, OUT


@lru_cache(maxsize=1)
def local_graph():
    import rdflib
    g = rdflib.Graph()
    path = OUT / "graph" / "graph.ttl"
    if not path.exists():
        raise SystemExit("output/graph/graph.ttl missing: run step2_mapping/run_mapping.py")
    print(f"  (loading {path.name} into memory, set FUSEKI_URL to use the server)")
    g.parse(path, format="turtle")
    return g


def select(query):
    """Return (column names, list of row dicts with plain string values)."""
    if FUSEKI_URL:
        r = requests.post(FUSEKI_URL.rstrip("/") + "/sparql", data={"query": query},
                          headers={"Accept": "application/sparql-results+json"}, timeout=300)
        r.raise_for_status()
        js = r.json()
        cols = js["head"]["vars"]
        rows = [{c: b[c]["value"] for c in cols if c in b} for b in js["results"]["bindings"]]
        return cols, rows
    res = local_graph().query(query)
    cols = [str(v) for v in res.vars]
    rows = [{c: (str(r[i]) if r[i] is not None else None) for i, c in enumerate(cols)} for r in res]
    return cols, rows
