# Web app for pipeline configuration

A scientist can configure pipeline parameters (topk, max_len, fraction_mask, n_variants_per_seed, etc.) and run the pipeline from a browser.

## Troubleshooting

### `ValueError: numpy.dtype size changed, may indicate binary incompatibility`

Some package (e.g. pandas or matplotlib) was built against a different numpy version than the one installed. Reinstall numpy first, then packages that use it:

```bash
pip install --upgrade --force-reinstall numpy
pip install --force-reinstall pandas matplotlib
streamlit run streamlit_app.py
```

If it still fails, use a **fresh venv** and install in this order so everything matches:

```bash
rm -rf .venv && python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install "numpy>=1.26,<2"
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-web-lite.txt
```

### `ImportError: numpy.core.multiarray failed to import`

This is a **numpy** (and often matplotlib) environment issue, not ESM2 or Hugging Face. It usually means numpy was built for a different Python or is mixed between conda/pip.

**Fix:**

```bash
# If using conda (Anaconda), reinstall numpy and matplotlib in one env
conda activate your_env
conda install numpy matplotlib --force-reinstall

# Or with pip in a clean venv (recommended to avoid conda/pip clashes)
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install --upgrade pip numpy matplotlib
pip install -r requirements.txt -r requirements-web.txt
```

Then run `streamlit run streamlit_app.py` again. If the error persists, use a **fresh virtual environment** and install only with pip (no conda in that env) so numpy and matplotlib match your Python 3.12.

### ESM2 / MetaLATTE: local vs Hugging Face

The **master** branch’s `run_metalatte_fasta.py` is **strict offline** and expects local folders (e.g. `MODEL_DIR`, `ESM_DIR`). To use **Hugging Face** for ESM2 (and optionally MetaLATTE) you’d need to change that script to load from `facebook/esm2_t33_650M_UR50D` and optionally `ChatterjeeLab/MetaLATTE` when those paths are not set. That’s a separate code change; the Streamlit app itself does not require ESM2 until you click “Run pipeline”.

### No space left on device / mini version on your machine

The full stack (PyTorch + CUDA, transformers, PepMLM, MetaLATTE, ESM2) needs several GB. You can run a **lite version** on your laptop:

1. **Free disk space**
   - Remove the failed venv: `rm -rf AML_Final_Project-master/.venv`
   - Clear pip cache: `pip cache purge`
   - Clear Hugging Face cache (if any): `rm -rf ~/.cache/huggingface` or similar
   - Remove other large, unneeded files or old venvs/conda envs

2. **Install CPU-only PyTorch** (saves a lot of space; no GPU needed for a “mini” run)
   ```bash
   cd AML_Final_Project-master
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install --upgrade pip
   pip install torch --index-url https://download.pytorch.org/whl/cpu
   pip install streamlit pandas matplotlib biopython transformers accelerate
   ```
   Then run the app as usual. Pipelines will be slower on CPU but will work.

3. **Keep runs small on your device**
   - Use **fewer variants** (e.g. variants per seed = 5–10, top K = 10).
   - Use a **small seed file** (e.g. 2–3 sequences) so PepMLM and MetaLATTE do less work.
   - Set **max_len** to 200–300 so long seeds are skipped.

4. **When to use cloud instead**
   - You need many variants, large seed sets, or fast turnaround → run the same app (or `pipeline_run.py`) on a cloud VM (GCP, AWS, Lambda, RunPod, etc.) or a lab server with more disk and optional GPU.
   - You can keep **config and small tests on your machine** and run **heavy jobs in the cloud** (e.g. copy config + seeds to the server, run pipeline there, download results).

## What’s included

- **`streamlit_app.py`** — Streamlit UI: choose seed file (predefined or upload), set sliders/inputs, run pipeline, view top variants + plot, download FASTA/CSV/PNG.
- **`pipeline_runner.py`** — Parameterized runner used by the app (and reusable by scripts): `PipelineConfig` + `run_pipeline(cfg)`.

## Run the app locally

1. **Install deps** (from project root `AML_Final_Project-master/`):

   ```bash
   pip install -r requirements.txt
   pip install torch transformers accelerate biopython streamlit
   ```

2. **Models and paths**

   - **PepMLM:** Put the PepMLM checkpoint in `PepMLM_local/` (or set the path in `PepMLM_gen_scripts/pepmlm_generate_fast.py`).
   - **MetaLATTE + ESM2:** The current `run_metalatte_fasta.py` uses hardcoded paths (e.g. `/workarea/AML_Final_Project/MetaLATTE` and `esm2_local/`). Either:
     - Set env vars before running so your MetaLATTE/ESM2 dirs are used (if the script is updated to read them), or
     - Edit the top of `MetaLATTE_gen_scripts/run_metalatte_fasta.py` so `MODEL_DIR` and `ESM_DIR` point to your local MetaLATTE and ESM2 folders.

3. **Launch Streamlit**

   ```bash
   cd AML_Final_Project-master
   streamlit run streamlit_app.py
   ```

   Open the URL shown (e.g. http://localhost:8501). Configure parameters, pick or upload a seed FASTA, click **Run pipeline**, then view and download results.

## Configurable parameters (in the UI)

| Parameter | Meaning |
|-----------|--------|
| **Variants per seed** | Number of sequence variants generated per seed protein. |
| **Fraction of positions to mask** | PepMLM masks this fraction of residues per variant (e.g. 0.10 = 10%). |
| **Top-K per mask (diversity)** | Sample from top K predictions at each mask; higher = more diversity. |
| **Max sequence length** | Seeds longer than this are skipped. |
| **Batch size** | Batch size for PepMLM generation. |
| **Top K binders to keep** | How many top MetaLATTE-predicted binders to save and plot. |
| **Run folder name** | Output directory under `pipeline_runs/`. |

## Deploying as a “real” website

- **Streamlit Cloud:** Push the repo to GitHub, connect at [share.streamlit.io](https://share.streamlit.io), point to `streamlit_app.py`. You’ll need to add Streamlit secrets or env for model paths if you don’t bake them in.
- **Server:** On a Linux server with GPU, run `streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0` and put a reverse proxy (nginx) or firewall in front. Use a process manager (systemd, supervisord) so it restarts on failure.
- **Alternative stack:** For a traditional web app (e.g. React frontend + REST API), add a **FastAPI** (or Flask) app that accepts a JSON config (same fields as `PipelineConfig`), enqueues a job (e.g. Celery + Redis), runs `run_pipeline(cfg)` in a worker, and exposes status + download URLs. The Streamlit app is the fastest way to get a working “website” for scientists without building that stack.

## Optional: API for other clients

You can expose the same pipeline via an HTTP API:

```python
# api_server.py (sketch)
from fastapi import FastAPI, BackgroundTasks
from pipeline_runner import PipelineConfig, run_pipeline

app = FastAPI()

@app.post("/run")
def run(config: dict, background_tasks: BackgroundTasks):
    cfg = PipelineConfig(work_dir=Path(config["work_dir"]), ...)
    job_id = str(uuid.uuid4())
    background_tasks.add_task(run_pipeline, cfg)
    return {"job_id": job_id, "status": "running"}
```

Then a minimal HTML/JS frontend could POST the config and poll for completion or download links.
