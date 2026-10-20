"""Step 5e: serve the access layer over HTTP, with the TEXT2SPARQL contract.

    python step5_llm/serve.py              # http://localhost:8000
    open:  http://localhost:8000/?question=How many contracts were terminated?&dataset=https://ul.edu.lb/kr/id/py/

Returns JSON {"dataset", "question", "query"}: the query itself is the evidence, anyone can run
it on the endpoint and check the answer. Extra fields: "status" (answered / refused), "reason"
when refused, and "rows" (the first 20 results) so a person can read the answer too.
Only the Python standard library is used, so nothing extra to install.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ask import ask, model  # noqa: E402

DATASET = "https://ul.edu.lb/kr/id/py/"
LLM = model()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        question = (qs.get("question") or [""])[0].strip()
        dataset = (qs.get("dataset") or [DATASET])[0]
        if not question:
            return self.reply(400, {"error": "add ?question=...", "example":
                                    "/?question=How many contracts were terminated?&dataset=" + DATASET})
        r = ask(question, LLM, verbose=False)
        body = {"dataset": dataset, "question": question, "query": r.get("query", ""), "status": r["status"]}
        if r["status"] in ("refused", "error"):
            body["reason"] = r.get("reason", "")
        else:
            body["rows"] = r["rows"][:20]
        self.reply(200, body)

    def reply(self, code, body):
        data = json.dumps(body, ensure_ascii=False, indent=1).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    host = os.environ.get("SERVE_HOST", "127.0.0.1")   # 127.0.0.1 only, unless inside Docker
    print(f"Serving on http://{host}:{port}/?question=...  (Ctrl+C to stop)", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
