# pipeline_run.py
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

from PepMLM_gen_scripts.pepmlm_generate_fast import PepMLMConfig, run_pepmlm
from MetaLATTE_gen_scripts.run_metalatte_fasta import run_metalatte_on_fasta

# ---------- CONFIG ----------

SEEDS_FASTA = Path("PepMLM_seeds/MT_seeds/MT_seeds_test.txt")
WORK_DIR    = Path("pipeline_runs/run1")

N_VARIANTS_PER_SEED = 50
FRACTION_MASK       = 0.10
TOPK_PER_MASK       = 5
MAX_LEN             = 400
BATCH_SIZE          = 8

TOP_K = 20   # how many best binders to visualize

# ---------- PIPELINE STEPS ----------

def step_generate_variants() -> Path:
    generated_fasta = WORK_DIR / "generated_variants.fasta"
    cfg = PepMLMConfig(
        fasta_in=SEEDS_FASTA,
        fasta_out=generated_fasta,
        n_variants_per_seed=N_VARIANTS_PER_SEED,
        fraction_mask=FRACTION_MASK,
        topk_per_mask=TOPK_PER_MASK,
        max_len=MAX_LEN,
        batch_size=BATCH_SIZE,
    )
    run_pepmlm(cfg)
    return generated_fasta

def step_predict_binding(variants_fasta: Path) -> Path:
    preds_csv = WORK_DIR / "metalatte_predictions.csv"
    preds_csv.parent.mkdir(parents=True, exist_ok=True)
    out_path = run_metalatte_on_fasta(
        fasta_path=str(variants_fasta),
        out_csv_path=str(preds_csv),
    )
    return Path(out_path)

def compute_binding_capacity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Define 'binding capacity' as the max probability over metal-binding
    classes, ignoring Non-binding.
    """
    metal_cols = [
        c for c in df.columns
        if c.startswith("prob_") and c not in ("prob_Non-binding", "prob_Non_binding")
    ]

    # score = max probability over metals
    df["binding_capacity"] = df[metal_cols].max(axis=1)

    # best metal label
    df["best_metal"] = df[metal_cols].idxmax(axis=1).str.replace("prob_", "")

    # also a compact text summary like your "top3" idea, but just top1 here
    df["best_metal_str"] = (
        df["best_metal"] + "=" + df["binding_capacity"].round(2).astype(str)
    )

    return df

def step_analyze_and_plot(preds_csv: Path) -> None:
    df = pd.read_csv(preds_csv)

    # compute binding capacity
    df = compute_binding_capacity(df)

    # sort and keep top K
    df_top = df.sort_values("binding_capacity", ascending=False).head(TOP_K)
    df_top.to_csv(WORK_DIR / "top_variants.csv", index=False)

    # bar plot of top variants
    plt.figure(figsize=(10, 5))
    plt.bar(df_top["id"].astype(str), df_top["binding_capacity"])
    plt.xticks(rotation=90)
    plt.ylabel("Binding capacity (max metal prob)")
    plt.title(f"Top {TOP_K} MetaLATTE-predicted binders")
    plt.tight_layout()

    plots_dir = WORK_DIR / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    out_png = plots_dir / "top_binding_capacity.png"
    plt.savefig(out_png, dpi=200)
    plt.close()

    print(f"Saved top {TOP_K} variants → {WORK_DIR / 'top_variants.csv'}")
    print(f"Saved plot → {out_png}")

def main():
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    print("Step 1: generating variants with PepMLM…")
    variants_fasta = step_generate_variants()

    print("Step 2: predicting binding with MetaLATTE…")
    preds_csv = step_predict_binding(variants_fasta)

    print("Step 3: analyzing & plotting top binders…")
    step_analyze_and_plot(preds_csv)

    print("Pipeline complete ✅")

if __name__ == "__main__":
    main()
