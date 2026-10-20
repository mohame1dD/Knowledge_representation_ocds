"""Show the gate blocking bad data: copy a chunk, break two rules on purpose, run the gate.

    python tools/gate_demo.py

Breaks rule 1 (a contract loses its award) and rule 3b (an award loses its supplier).
The gate must print GATE FAILED and exit 1.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import rdflib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import OUT, PPO  # noqa: E402

src = sorted((OUT / "graph" / "chunks").glob("*.ttl"))[0]
g = rdflib.Graph().parse(src, format="turtle")
P = rdflib.Namespace(PPO)
removed = [sorted(g.triples((None, P.basedOnAward, None)))[0], sorted(g.triples((None, P.awardedTo, None)))[0]]
print("Removing:")
for t in removed:
    g.remove(t)
    print("  ", " ".join(x.n3(g.namespace_manager)[:90] for x in t))
tmp = Path(tempfile.gettempdir()) / "bad_commit.ttl"
g.serialize(tmp, format="turtle")
gate = Path(__file__).resolve().parent / "gate.py"
r = subprocess.run([sys.executable, str(gate), str(tmp)])
print(f"\nGate exit code on the broken file: {r.returncode} (1 = blocked, as intended)")
sys.exit(0 if r.returncode == 1 else 1)
