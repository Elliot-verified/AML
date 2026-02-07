#!/bin/bash
# Use a project venv so we don't hit conda's numpy/sklearn/pyarrow mismatch.
# Run from AML_Final_Project-master:  bash setup_venv.sh

set -e
cd "$(dirname "$0")"

echo "Removing old .venv if present..."
rm -rf .venv

echo "Creating fresh venv..."
python3 -m venv .venv
source .venv/bin/activate

echo "Installing pip and numpy first (must match sklearn/pyarrow)..."
pip install --upgrade pip
pip install "numpy>=2"

echo "Installing PyTorch (CPU)..."
pip install torch --index-url https://download.pytorch.org/whl/cpu

echo "Installing rest of deps..."
pip install streamlit pandas matplotlib transformers accelerate biopython

echo ""
echo "Done. Activate and run:"
echo "  source .venv/bin/activate"
echo "  streamlit run streamlit_app.py"
echo ""
echo "On Windows: .venv\\Scripts\\activate then streamlit run streamlit_app.py"
