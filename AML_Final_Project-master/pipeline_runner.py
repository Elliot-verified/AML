"""
Parameterized pipeline runner for use by CLI or web app.
Runs: PepMLM (generate variants) → MetaLATTE (predict binding) → analyze & plot.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

from PepMLM_gen_scripts.pepmlm_generate_fast import PepMLMConfig, run_pepmlm


@dataclass
class PipelineConfig:
    """All knobs a scientist might want to configure."""
    seed_fasta: Path
    work_dir: Path
    n_variants_per_seed: int = 20
    fraction_mask: float = 0.10
    topk_per_mask: int = 5
    max_len: int = 400
    batch_size: int = 8
    top_k: int = 20  # how many top binders to keep and plot


def compute_binding_capacity(df: pd.DataFrame) -> pd.DataFrame:
    """Add binding_capacity, best_metal, best_metal_str from prob_* columns."""
    metal_cols = [
        c for c in df.columns
        if c.startswith("prob_") and c not in ("prob_Non-binding", "prob_Non_binding")
    ]
    if not metal_cols:
        return df
    df = df.copy()
    df["binding_capacity"] = df[metal_cols].max(axis=1)
    df["best_metal"] = df[metal_cols].idxmax(axis=1).str.replace("prob_", "")
    df["best_metal_str"] = (
        df["best_metal"] + "=" + df["binding_capacity"].round(2).astype(str)
    )
    return df


def run_pipeline(cfg: PipelineConfig) -> dict[str, Path]:
    """
    Run the full pipeline with the given config.
    Returns dict of output paths: generated_fasta, predictions_csv, top_csv, plot_png.
    """
    work_dir = Path(cfg.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    generated_fasta = work_dir / "generated_variants.fasta"
    pep_cfg = PepMLMConfig(
        fasta_in=Path(cfg.seed_fasta),
        fasta_out=generated_fasta,
        n_variants_per_seed=cfg.n_variants_per_seed,
        fraction_mask=cfg.fraction_mask,
        topk_per_mask=cfg.topk_per_mask,
        max_len=cfg.max_len,
        batch_size=cfg.batch_size,
    )
    run_pepmlm(pep_cfg)

    # Lazy import so the app can load even when MetaLATTE/ESM paths are not set yet
    from MetaLATTE_gen_scripts.run_metalatte_fasta import run_metalatte_on_fasta

    preds_csv = work_dir / "metalatte_predictions.csv"
    run_metalatte_on_fasta(
        fasta_path=str(generated_fasta),
        out_csv_path=str(preds_csv),
    )

    df = pd.read_csv(preds_csv)
    df = compute_binding_capacity(df)
    df_top = df.sort_values("binding_capacity", ascending=False).head(cfg.top_k)
    top_csv = work_dir / "top_variants.csv"
    df_top.to_csv(top_csv, index=False)

    # Defer matplotlib import so the app loads even if numpy/matplotlib are broken
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plots_dir = work_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    plot_png = plots_dir / "top_binding_capacity.png"
    plt.figure(figsize=(10, 5))
    plt.bar(df_top["id"].astype(str), df_top["binding_capacity"])
    plt.xticks(rotation=90)
    plt.ylabel("Binding capacity (max metal prob)")
    plt.title(f"Top {cfg.top_k} MetaLATTE-predicted binders")
    plt.tight_layout()
    plt.savefig(plot_png, dpi=200)
    plt.close()

    return {
        "generated_fasta": generated_fasta,
        "predictions_csv": preds_csv,
        "top_csv": top_csv,
        "plot_png": plot_png,
    }
