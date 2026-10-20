#!/usr/bin/env bash
# Creates the project's virtual environment in .venv and installs every library.
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install --no-deps morph-kgc==2.8.1
[ -f .env ] || cp .env.example .env
echo "Done. Activate with: source .venv/bin/activate"
