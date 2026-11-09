#!/usr/bin/env bash
# Contract: ./run.sh <SIM_URL> starts the controller and runs until the scenario finishes - no manual steps.
#
# Runtime: plain Python >= 3.10. The controller needs only `httpx` and `pyyaml` (stdlib sqlite3 for state); numpy/fastapi/uvicorn
# in requirements.txt are for the simulator and the tests. Docker is OPTIONAL and not needed to run: a Dockerfile is provided
# for operators (`docker build -t formi-controller . && docker run --network host formi-controller <SIM_URL>`).
# Tested on a 4 vCPU / 8 GB class box: peak RSS of the controller is < 1 GB on the 650k-dials/day load scenario.
set -euo pipefail
SIM_URL="${1:?usage: ./run.sh <SIM_URL>}"
cd "$(dirname "$0")"
export PYTHONHASHSEED=0                      # decisions never depend on hash order, but make the run bit-reproducible anyway
export PYTHONUNBUFFERED=1
mkdir -p state
PY="${PYTHON:-python3}"
if ! "$PY" -c "import httpx, yaml" 2>/dev/null; then
  if [ ! -x .venv/bin/python ]; then "$PY" -m venv .venv; fi
  .venv/bin/pip install -q -r requirements.txt
  PY=.venv/bin/python
fi
# state/controller.db is resumable: kill -9 and re-run this same command and it continues (see reports/crash_recovery_*.md).
# A db that belongs to a different scenario / a restarted simulator is detected and moved aside automatically.
exec "$PY" -m controller.main --url "$SIM_URL" --db "${CONTROLLER_DB:-state/controller.db}" \
     --archive "${CONTROLLER_ARCHIVE:-state/exposure_archive}" ${CONTROLLER_PORT:+--status-port "$CONTROLLER_PORT"}
