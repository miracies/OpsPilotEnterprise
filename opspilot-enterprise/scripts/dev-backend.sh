#!/usr/bin/env bash
# OpsPilot Enterprise - Start all backend services for local development
# Run from the repository root: bash scripts/dev-backend.sh
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Installing shared schema ==="
pip install -e "$ROOT/packages/shared-schema" > /dev/null 2>&1

declare -A SERVICES=(
  ["tool-gateway"]=8020
  ["vmware-skill-gateway"]=8030
  ["change-impact-service"]=8040
  ["evidence-aggregator"]=8050
  ["event-ingestion-service"]=8060
  ["langgraph-orchestrator"]=8010
)

PIDS=()

cleanup() {
  echo "Stopping all services..."
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null; done
  exit 0
}
trap cleanup INT TERM

for svc in "${!SERVICES[@]}"; do
  port=${SERVICES[$svc]}
  dir="$ROOT/services/$svc"
  echo "Starting $svc on port $port..."
  pip install -e "$dir" > /dev/null 2>&1
  (cd "$dir" && uvicorn app.main:app --host 0.0.0.0 --port "$port" --reload) &
  PIDS+=($!)
done

echo "Starting api-bff on port 8000..."
pip install -e "$ROOT/apps/api-bff" > /dev/null 2>&1
(cd "$ROOT/apps/api-bff" && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload) &
PIDS+=($!)

echo ""
echo "=== All services started ==="
echo "  API BFF:           http://localhost:8000"
echo "  Orchestrator:      http://localhost:8010"
echo "  Tool Gateway:      http://localhost:8020"
echo "  VMware Gateway:    http://localhost:8030"
echo "  Change Impact:     http://localhost:8040"
echo "  Evidence Agg:      http://localhost:8050"
echo "  Event Ingestion:   http://localhost:8060"
echo ""
echo "Press Ctrl+C to stop all services."

wait
