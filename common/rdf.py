"""IRI scheme and triple-writing helpers, used by the Step 2 database loader and entity resolution.

IRI scheme (the same templates are written in step2_mapping/mapping.r2rml.ttl):
    process   https://ul.edu.lb/kr/id/py/process/{ocid}
    tender    https://ul.edu.lb/kr/id/py/tender/{ocid}            one call per process
    award     https://ul.edu.lb/kr/id/py/award/{ocid}/{award id}  id only unique inside a process
    contract  https://ul.edu.lb/kr/id/py/contract/{ocid}/{contract id}
    org       https://ul.edu.lb/kr/id/py/org/{party id}           e.g. PY-RUC-80002756-6, stable across processes
    method    https://ul.edu.lb/kr/id/py/method/{slug of the label}

Why: every IRI is built from the source's own identifiers, so the same row
always gets the same name (rebuilds are deterministic) and a second source
using RUC numbers can point at the same organisation.
"""
import re
import unicodedata
from urllib.parse import quote

from common.config import ID, PPO

XSD = "http://www.w3.org/2001/XMLSchema#"
RDF_TYPE = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
RDFS_LABEL = "<http://www.w3.org/2000/01/rdf-schema#label>"
SKOS_PREF = "<http://www.w3.org/2004/02/skos/core#prefLabel>"


def enc(s):
    return quote(str(s).strip(), safe="-_.~")


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def process(ocid): return f"<{ID}process/{enc(ocid)}>"
def tender(ocid): return f"<{ID}tender/{enc(ocid)}>"
def award(ocid, aid): return f"<{ID}award/{enc(ocid)}/{enc(aid)}>"
def contract(ocid, cid): return f"<{ID}contract/{enc(ocid)}/{enc(cid)}>"
def org(pid): return f"<{ID}org/{enc(pid)}>"
def method(label): return f"<{ID}method/{slug(label)}>"
def p(name): return f"<{PPO}{name}>"


def lit(v, dtype=None):
    s = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
    return f'"{s}"^^<{XSD}{dtype}>' if dtype else f'"{s}"'


def dec(v):
    """Decimal literal without exponent or trailing .0 noise."""
    try:
        d = format(float(v), "f").rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return None
    return lit(d or "0", "decimal")


def present(v):
    return v is not None and v == v and str(v).strip() != ""
