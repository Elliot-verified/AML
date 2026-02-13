"""
Web UI for the metal-binding pipeline.
Scientists configure: topk, max_len, fraction_mask, n_variants_per_seed, etc.,
then run the pipeline and download results.

Run from project root (AML_Final_Project-master):
  streamlit run streamlit_app.py

Requires: PepMLM_local, MetaLATTE and ESM2 dirs (see WEB_APP.md).
"""
from pathlib import Path
import tempfile
import sys
from typing import Optional

import streamlit as st
import pandas as pd

# Project root = directory containing this file
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline_runner import PipelineConfig, run_pipeline

SEEDS_DIR = PROJECT_ROOT / "PepMLM_seeds"
PIPELINE_RUNS = PROJECT_ROOT / "pipeline_runs"


def list_predefined_seeds() -> list[tuple[str, Path]]:
    """Return [(label, path), ...] for all FASTA-like files under PepMLM_seeds."""
    out = []
    if not SEEDS_DIR.exists():
        return out
    for path in sorted(SEEDS_DIR.rglob("*")):
        if path.is_file() and path.suffix.lower() in (".fasta", ".fa", ".txt"):
            try:
                rel = path.relative_to(PROJECT_ROOT)
                out.append((str(rel), path))
            except ValueError:
                out.append((path.name, path))
    return out


st.set_page_config(
    page_title="Metal-binding pipeline",
    page_icon="🧬",
    layout="wide",
)

st.title("🧬 Metal-binding protein design pipeline")
st.caption("Configure parameters, run PepMLM → MetaLATTE, and download top variants.")

predefined = list_predefined_seeds()
seed_source = st.radio(
    "Seed sequences",
    options=["Use a predefined seed file", "Upload my own FASTA"],
    horizontal=True,
)

seed_path: Optional[Path] = None
if seed_source == "Use a predefined seed file":
    if not predefined:
        st.warning("No predefined seeds found under `PepMLM_seeds/`. Upload a FASTA or add files there.")
    else:
        chosen = st.selectbox(
            "Choose seed file",
            options=[label for label, _ in predefined],
            format_func=lambda x: x,
        )
        seed_path = next(p for l, p in predefined if l == chosen)
else:
    uploaded = st.file_uploader("Upload FASTA", type=["fasta", "fa", "txt"])
    if uploaded:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".fasta", delete=False) as f:
            f.write(uploaded.read())
            seed_path = Path(f.name)
    else:
        st.info("Upload a FASTA file to use as seeds.")

st.divider()
st.subheader("Pipeline parameters")

col1, col2, col3 = st.columns(3)

with col1:
    n_variants_per_seed = st.number_input(
        "Variants per seed",
        min_value=1,
        max_value=200,
        value=20,
        help="Number of sequence variants to generate per seed protein.",
    )
    fraction_mask = st.slider(
        "Fraction of positions to mask",
        min_value=0.01,
        max_value=0.30,
        value=0.10,
        step=0.01,
        format="%.2f",
        help="PepMLM masks this fraction of residues per variant.",
    )
    topk_per_mask = st.number_input(
        "Top-K per mask (diversity)",
        min_value=1,
        max_value=20,
        value=5,
        help="Higher = more diverse variants (sampling from top K predictions).",
    )

with col2:
    max_len = st.number_input(
        "Max sequence length",
        min_value=50,
        max_value=800,
        value=400,
        help="Seeds longer than this are skipped.",
    )
    batch_size = st.number_input(
        "Batch size",
        min_value=1,
        max_value=32,
        value=8,
        help="Batch size for PepMLM generation.",
    )
    top_k = st.number_input(
        "Top K binders to keep",
        min_value=5,
        max_value=100,
        value=20,
        help="How many top MetaLATTE-predicted binders to save and plot.",
    )

run_dir_name = st.text_input(
    "Run folder name (under pipeline_runs/)",
    value="web_run",
    help="Optional: name for this run’s output folder.",
)

st.divider()

if st.button("Run pipeline", type="primary", use_container_width=True):
    if seed_path is None or not Path(seed_path).exists():
        st.error("Please choose or upload a seed FASTA first.")
    else:
        work_dir = PIPELINE_RUNS / run_dir_name
        cfg = PipelineConfig(
            seed_fasta=Path(seed_path),
            work_dir=work_dir,
            n_variants_per_seed=n_variants_per_seed,
            fraction_mask=fraction_mask,
            topk_per_mask=topk_per_mask,
            max_len=max_len,
            batch_size=batch_size,
            top_k=top_k,
        )
        with st.spinner("Running pipeline (PepMLM → MetaLATTE → analysis). This may take a few minutes."):
            try:
                outputs = run_pipeline(cfg)
            except Exception as e:
                st.exception(e)
                st.stop()

        st.success("Pipeline complete.")

        df_top = pd.read_csv(outputs["top_csv"])
        st.subheader("Top variants by binding capacity")
        st.dataframe(df_top, use_container_width=True)

        st.subheader("Binding capacity plot")
        st.image(str(outputs["plot_png"]), use_container_width=True)

        st.subheader("Download results")
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            with open(outputs["generated_fasta"]) as f:
                st.download_button("Generated variants (FASTA)", f.read(), file_name="generated_variants.fasta")
        with d2:
            with open(outputs["predictions_csv"]) as f:
                st.download_button("MetaLATTE predictions (CSV)", f.read(), file_name="metalatte_predictions.csv")
        with d3:
            with open(outputs["top_csv"]) as f:
                st.download_button("Top variants (CSV)", f.read(), file_name="top_variants.csv")
        with d4:
            with open(outputs["plot_png"], "rb") as f:
                st.download_button("Plot (PNG)", f.read(), file_name="top_binding_capacity.png")

        st.caption(f"Outputs also saved under: `{work_dir}`")
