#!/usr/bin/env zsh
set -euo pipefail

# Root of the repository (this script lives in repo root)
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "Starting frontend (npm run dev) and backend (python manage.py runserver)..."

# Start frontend in background
(
  cd frontend || { echo "frontend directory not found"; exit 1 }
  npm run dev
) &
FRONTEND_PID=$!

# Start backend in background
(
  cd "$ROOT" || exit 1
  # Use python3 to be explicit; change to `python` if needed
  python3 manage.py runserver 0.0.0.0:8000
) &
BACKEND_PID=$!

cleanup() {
  echo "Stopping frontend (PID $FRONTEND_PID) and backend (PID $BACKEND_PID)..."
  kill "$FRONTEND_PID" "$BACKEND_PID" 2>/dev/null || true
  wait "$FRONTEND_PID" "$BACKEND_PID" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

# Wait for background processes
wait
