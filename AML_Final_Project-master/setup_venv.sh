#!/bin/bash
set -e
cd "$(dirname "$0")"
echo "Removing old .venv if present..."
rm -rf .venv
echo "Creating fresh venv..."
python3 -m venv .venv
PIP=".venv/bin/pip"
echo "Installing pip and numpy first..."
"$PIP" install --upgrade pip
"$PIP" install "numpy>=2"
echo "Installing PyTorch (CPU)..."
"$PIP" install torch --index-url https://download.pytorch.org/whl/cpu
echo "Installing rest of deps..."
"$PIP" install streamlit pandas matplotlib transformers accelerate biopython
echo "Done. Run the app with:  bash run_app.sh"
echo "Or:  .venv/bin/python -m streamlit run streamlit_app.py"
