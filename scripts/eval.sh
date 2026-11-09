#!/usr/bin/env bash
# Run one scenario end to end: baseline (cached) -> sim server -> controller -> grade.
#   scripts/eval.sh public_02_incidents [port] [extra controller args...]
set -euo pipefail
cd "$(dirname "$0")/.."
NAME="${1:?scenario name, e.g. public_01_dev}"; PORT="${2:-8700}"; shift || true; shift || true
PY="${PYTHON:-.venv/bin/python}"
SC="scenarios/${NAME}.yaml"
mkdir -p runs reports state
[ -d "runs/base_${NAME}/_truth" ] || $PY -m sim baseline --scenario "$SC" --run-dir "runs/base_${NAME}" >/dev/null
rm -rf "runs/mine_${NAME}" "state/${NAME}.db"*
$PY -m sim serve --scenario "$SC" --run-dir "runs/mine_${NAME}" --force --port "$PORT" >"state/sim_${NAME}.log" 2>&1 &
SIM=$!
trap 'kill $SIM 2>/dev/null || true' EXIT
for _ in $(seq 1 60); do curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null && break; sleep 0.5; done
/usr/bin/time -p $PY -m controller.main --url "http://127.0.0.1:${PORT}" --db "state/${NAME}.db" "$@" 2>&1 | grep -E "ERROR|Traceback|finished|real" || true
$PY -m sim grade --run "runs/mine_${NAME}" --baseline "runs/base_${NAME}" --out "reports/${NAME}.md" >/dev/null
sed -n 5,12p "reports/${NAME}.md"; grep -E "applied —|harmful|Credits" "reports/${NAME}.md" || true
