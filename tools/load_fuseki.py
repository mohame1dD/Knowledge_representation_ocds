"""Upload the ontology, the graph and the entity-resolution links to Fuseki.

    python tools/load_fuseki.py [http://localhost:3030/procurement]

The password comes from FUSEKI_ADMIN_PASSWORD in .env (never written in a file in git).
Waits up to 3 minutes for Fuseki to start, so the Docker stack can call it right away.
The first file REPLACES the default graph (HTTP PUT), the others are added (POST), so
running it twice does not leave old data behind.
"""
import os
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import FUSEKI_URL, OUT, ROOT  # noqa: E402

url = (sys.argv[1] if len(sys.argv) > 1 else FUSEKI_URL or "http://localhost:3030/procurement").rstrip("/")
password = os.environ.get("FUSEKI_ADMIN_PASSWORD", "").strip()
if not password:
    raise SystemExit("Set FUSEKI_ADMIN_PASSWORD in .env (the same one the fuseki container uses)")
auth = ("admin", password)

print(f"Waiting for Fuseki at {url}", flush=True)
for i in range(90):
    try:
        if requests.get(url.rsplit("/", 1)[0] + "/$/ping", timeout=3).ok:
            break
    except requests.RequestException:
        pass
    time.sleep(2)
else:
    raise SystemExit("Fuseki did not answer within 3 minutes")

files = [(ROOT / "step3_ontology" / "ppo.ttl", "text/turtle"),
         (OUT / "graph" / "graph.ttl", "text/turtle"),
         (OUT / "graph" / "sameas.ttl", "text/turtle")]
first = True
for f, ctype in files:
    if not f.exists():
        print(f"skip {f.name} (missing)")
        continue
    t = time.time()
    with open(f, "rb") as fh:
        method = requests.put if first else requests.post
        r = method(f"{url}/data?default", data=fh, headers={"Content-Type": ctype}, auth=auth, timeout=3600)
    print(f"{f.name}: HTTP {r.status_code} in {time.time() - t:.0f}s", flush=True)
    if r.status_code == 401:
        raise SystemExit("Fuseki refused the password: FUSEKI_ADMIN_PASSWORD must match the container's")
    r.raise_for_status()
    first = False
print(f"Done. Endpoint: {url}/sparql")
