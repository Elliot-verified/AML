# ML Pipelines Overview (master branch)

This folder contains **several ML pipelines** for metal-binding protein design: **PepMLM** (variant generation) → **MetaLATTE** (metal-binding prediction) → optional **BLAST** (novelty). Below is what each entry point does and how they differ.

---

## 1. **`pipeline_run.py`** — Single-script, one seed file

**What it does:** One linear pipeline for a single seed FASTA.

| Step | Action |
|------|--------|
| 1 | **PepMLM**: generate variants from `PepMLM_seeds/MT_seeds/MT_seeds_test.txt` → `pipeline_runs/run1/generated_variants.fasta` |
| 2 | **MetaLATTE**: predict metal-binding probs on those variants → `metalatte_predictions.csv` |
| 3 | **Analyze**: compute “binding capacity” (max metal prob), keep top 20, bar plot → `top_variants.csv`, `plots/top_binding_capacity.png` |

**Config (top of file):** `SEEDS_FASTA`, `WORK_DIR`, `N_VARIANTS_PER_SEED`, `FRACTION_MASK`, `TOPK_PER_MASK`, `MAX_LEN`, `BATCH_SIZE`, `TOP_K`.

**Run:** `python pipeline_run.py`

**Note:** `step_predict_binding` is defined twice in the file; the second definition uses `fasta_in` / `out_csv` (and `device`). The MetaLATTE helper `run_metalatte_on_fasta` in `MetaLATTE_gen_scripts/run_metalatte_fasta.py` expects `fasta_path` and `out_csv_path`, so the first definition matches that; the second would need the wrapper to pass the right kwargs.

---

## 2. **`pipeline.ipynb`** — Notebook, multiple seed sets + inline novelty

**What it does:** Same PepMLM → MetaLATTE flow as above, but over **multiple seed sets** (e.g. `pb_mer_operon`, `hg_specific`, `cd_specific`). For each seed set it:

- Runs PepMLM → writes `notebook_runs/<run_name>/seed_<name>/generated_variants.fasta`
- Runs MetaLATTE → `metalatte_predictions.csv`
- Computes **novelty vs seeds** (identity/similarity) and saves a histogram (e.g. `identity_hist_<seed_set>.png`)

So this is the “multi–seed set” pipeline with **inline** similarity/novelty analysis (no BLAST).

---

## 3. **`Pipelines/pipeline_blast.ipynb`** — Multi–seed set + **post-hoc BLAST novelty**

**What it does:** Structured version of the same idea with **BLAST-based novelty** added after the fact.

- **Data structures:** `SeedSet` (name + path to seed FASTA), `PepMLMParams`, `RunConfig` (name, out_dir, PepMLM params, novelty threshold, top_k).
- **Flow:**
  - For each seed set: PepMLM → MetaLATTE → binding metrics (`binding_capacity`, `best_metal`) → per–seed-set CSVs and a **combined FASTA** of all variants.
  - Saves `all_variants_with_scores.csv` and **`all_variants_for_blast.fasta`** for the run.
- **Post-hoc:** You run BLAST yourself (e.g. `makeblastdb` on seeds, `blastp` query = `all_variants_for_blast.fasta`). Then `add_novelty_from_blast(run_cfg, blast_tsv)` loads the BLAST results (outfmt 6), merges max % identity per variant, and writes `all_variants_with_scores_and_novelty.csv` with `is_novel` (e.g. identity &lt; 0.95).

So this pipeline = **PepMLM + MetaLATTE + optional BLAST novelty**, with configurable seed sets and run directories.

---

## 4. **`Pipelines/single_cell_pipeline.ipynb`** — Same multi–seed set flow, different name

**What it does:** Same structure as the BLAST pipeline (multiple `SeedSet`s, `run_experiment`, PepMLM → MetaLATTE). From the saved outputs it also computes **novelty vs seeds** and saves identity histograms (like `pipeline.ipynb`). The name “single_cell” likely means “one experiment/run” or “one notebook cell” rather than single-cell RNA-seq.

---

## Shared components

| Component | Role |
|-----------|------|
| **`PepMLM_gen_scripts/pepmlm_generate_fast.py`** | `PepMLMConfig` dataclass + `run_pepmlm(cfg)`. Loads local PepMLM, generates variants from a seed FASTA, writes FASTA. Uses `PepMLM_local` (no HF fallback in this version). |
| **`MetaLATTE_gen_scripts/run_metalatte_fasta.py`** | `run_metalatte_on_fasta(fasta_path, out_csv_path)`. **Strict offline**: sets env to disable network, loads local ESM2 + MetaLATTE from paths like `/workarea/AML_Final_Project/MetaLATTE` and `/workarea/.../esm2_local/esm2_t33_650M_UR50D`. Reads FASTA, runs batches, writes CSV with `id`, `sequence`, and `prob_<metal>` columns. |
| **`MetaLATTE_gen_scripts/run_metalatte_inference.py`** | Alternative CLI: `--fasta`, `--out`, `--model_dir`, `--esm_dir`. Tries to discover a `predict`/`predict_proba` from the MetaLATTE module; more exploratory. |

---

## Seed and output layout (master)

- **Seeds:**  
  - `PepMLM_seeds/MT_seeds/` — e.g. `MT_seeds_test.txt`, `MT_Bacterial_Redox.fasta`, `MT_Bacterial_transformation.fasta`  
  - `PepMLM_seeds/Metal_specific/` — `cd_seeds.fasta`, `hg_seeds.fasta`, `pb_seeds.fasta`  
  - `PepMLM_seeds/seeds.txt`  
- **Outputs:**  
  - `PepMLM_Outputs/` — generated variant FASTAs  
  - `MetaLATTE_Outputs/` — MetaLATTE prediction CSVs  
  - `notebook_runs/` or `pipeline_runs/` — per-run dirs with generated_variants.fasta, metalatte_predictions.csv, top_variants, plots, and (in BLAST pipeline) `all_variants_for_blast.fasta` and novelty CSV.

---

## Differences from main (old version you had)

- **Master** has: `pipeline_run.py`, `pipeline.ipynb`, `Pipelines/pipeline_blast.ipynb`, `Pipelines/single_cell_pipeline.ipynb`, and the **MetaLATTE_gen_scripts** (run_metalatte_fasta + run_metalatte_inference), plus the **PepMLMConfig**-based `pepmlm_generate_fast.py` and multiple seed sets (Metal_specific, MT_seeds).
- **Main** had: only `gen_scripts/` (PepMLM, no MetaLATTE runner), `parsing/`, one `stream.txt` seed set, and no top-level pipeline script or BLAST/novelty notebooks.

So the **master** branch is the one with the full set of ML pipelines (PepMLM → MetaLATTE → optional BLAST/novelty) and multiple seed files.
