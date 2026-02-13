#!/bin/bash
cd "$(dirname "$0")"
if [ ! -f .venv/bin/python ]; then
  echo "Project venv not found. Run first:  bash setup_venv.sh"
  exit 1
fi
.venv/bin/python -m streamlit run streamlit_app.py "$@"
