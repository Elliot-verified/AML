"""
Web UI for the metal-binding pipeline.
Scientists configure: topk, max_len, fraction_mask, n_variants_per_seed, etc.,
then run the pipeline and download results.

Run from project root (AML_Final_Project-master):
  streamlit run streamlit_app.py

Pipeline runs in a background subprocess so the page does not time out.
Use "Check for results" to see output when ready.

Requires: PepMLM_local, MetaLATTE and ESM2 dirs (see WEB_APP.md).
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
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

if "pipeline_work_dir" not in st.session_state:
    st.session_state.pipeline_work_dir = None

if st.button("Run pipeline", type="primary", use_container_width=True):
    if seed_path is None or not Path(seed_path).exists():
        st.error("Please choose or upload a seed FASTA first.")
    else:
        work_dir = PIPELINE_RUNS / run_dir_name
        work_dir.mkdir(parents=True, exist_ok=True)
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
        config_file = work_dir / "run_config.json"
        with open(config_file, "w") as f:
            json.dump(cfg.to_dict(), f, indent=2)
        with open(work_dir / "run_stdout.txt", "w") as out, open(work_dir / "run_stderr.txt", "w") as err:
            proc = subprocess.Popen(
                [sys.executable, "-m", "pipeline_runner", str(config_file)],
                cwd=str(PROJECT_ROOT),
                stdout=out,
                stderr=err,
            )
        st.session_state.pipeline_work_dir = work_dir
        st.session_state.pipeline_process = proc
        st.success(f"Pipeline started in the background (run folder: `{run_dir_name}`). It may take several minutes. Click **Check for results** below to see when it's done.")

st.divider()
st.subheader("Check for results")

# Allow checking a specific run folder (default: last started)
check_dir_name = st.text_input("Run folder to check", value=run_dir_name, key="check_run_dir")
check_dir = PIPELINE_RUNS / check_dir_name

if check_dir.exists():
    top_csv = check_dir / "top_variants.csv"
    plot_png = check_dir / "plots" / "top_binding_capacity.png"
    if top_csv.exists() and plot_png.exists():
        st.success("Pipeline completed. Showing results.")
        df_top = pd.read_csv(top_csv)
        st.dataframe(df_top, use_container_width=True)
        st.image(str(plot_png), use_container_width=True)
        d1, d2, d3, d4 = st.columns(4)
        gen_fasta = check_dir / "generated_variants.fasta"
        pred_csv = check_dir / "metalatte_predictions.csv"
        with d1:
            if gen_fasta.exists():
                with open(gen_fasta) as f:
                    st.download_button("Generated variants (FASTA)", f.read(), file_name="generated_variants.fasta", key="dl_fasta")
        with d2:
            if pred_csv.exists():
                with open(pred_csv) as f:
                    st.download_button("MetaLATTE predictions (CSV)", f.read(), file_name="metalatte_predictions.csv", key="dl_pred")
        with d3:
            with open(top_csv) as f:
                st.download_button("Top variants (CSV)", f.read(), file_name="top_variants.csv", key="dl_top")
        with d4:
            with open(plot_png, "rb") as f:
                st.download_button("Plot (PNG)", f.read(), file_name="top_binding_capacity.png", key="dl_plot")
        st.caption(f"Outputs saved under: `{check_dir}`")
    else:
        proc = st.session_state.get("pipeline_process")
        if proc is not None and st.session_state.get("pipeline_work_dir") == check_dir and proc.poll() is None:
            st.info("Pipeline still running. Refresh this page or click **Check for results** again in a few minutes.")
        else:
            st.warning("No results yet for this run. If you just started the pipeline, wait a few minutes and check again. You can also look at the run folder for logs: `run_stdout.txt` and `run_stderr.txt`.")
else:
    st.info("Enter a run folder name (e.g. web_run) and we'll look for results under `pipeline_runs/`.")
