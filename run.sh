#!/usr/bin/env bash
# Build the warehouse end to end (no dbt required):
#   ./run.sh
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Building the warehouse (ingest -> load -> transform -> checks)"
python build.py

echo ""
echo "==> Done. Launch the dashboard with:  streamlit run app/dashboard.py"
