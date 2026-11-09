#!/usr/bin/env bash
# Load evidence on public_03_load: wall time, ingest throughput, decision lag, peak memory -> reports/load_public_03.md
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-.venv/bin/python}"; PORT="${1:-8703}"; NAME=public_03_load
export PYTHONHASHSEED=0
[ -d "runs/base_${NAME}/_truth" ] || $PY -m sim baseline --scenario scenarios/${NAME}.yaml --run-dir runs/base_${NAME} >/dev/null
rm -rf runs/mine_${NAME} state/${NAME}.db* state/load_arch
$PY -m sim serve --scenario scenarios/${NAME}.yaml --run-dir runs/mine_${NAME} --force --port $PORT >state/sim_${NAME}.log 2>&1 &
SIM=$!; trap 'kill $SIM 2>/dev/null || true' EXIT
for _ in $(seq 1 120); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; sleep 0.5; done
if /usr/bin/time -l true 2>/dev/null; then TIMEV="/usr/bin/time -l"; else TIMEV="/usr/bin/time -v"; fi
$TIMEV $PY -m controller.main --url http://127.0.0.1:$PORT --db state/${NAME}.db --archive state/load_arch 2>state/load_time.txt >/dev/null || true
$PY -m sim grade --run runs/mine_${NAME} --baseline runs/base_${NAME} --out reports/${NAME}.md >/dev/null
$PY scripts/load_report.py state/${NAME}.db state/load_time.txt reports/load_${NAME}.md
