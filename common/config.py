"""One place for settings. Reads .env (or .env.example) at the repo root."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env") or load_dotenv(ROOT / ".env.example")
except ImportError:  # still works without python-dotenv, using defaults
    pass


def _get(name, default=""):
    return os.environ.get(name, default).strip()


YEARS = [int(y) for y in _get("YEARS", "2019,2020,2021,2022").split(",") if y.strip()]
DATA_DIR = ROOT / _get("DATA_DIR", "data/raw")
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

SHACL_BATCH = int(_get("SHACL_BATCH", "2000"))
REASONER_SAMPLE = int(_get("REASONER_SAMPLE", "300"))
FUSEKI_URL = _get("FUSEKI_URL")

LLM_MODE = _get("LLM_MODE", "replay")
ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = _get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
GEMINI_API_KEY = _get("GEMINI_API_KEY")
GEMINI_MODEL = _get("GEMINI_MODEL", "gemini-flash-latest")
LLM_DELAY = float(_get("LLM_DELAY", "0") or 0)   # seconds to wait before each model call



# Namespaces shared by every step
BASE = "https://ul.edu.lb/kr/"
PPO = BASE + "ont/ppo#"          # our ontology
ID = BASE + "id/py/"             # our data (py = Paraguay)
