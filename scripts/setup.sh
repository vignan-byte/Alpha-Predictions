#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
[ -f backend/.env ] || cp backend/.env.example backend/.env
(cd frontend && npm ci && npm run build)
(cd backend && ../.venv/bin/python -c 'from app.database.store import init_db; init_db()')
echo 'Run: bash scripts/run.sh'
