# Running the pipeline in the cloud

So the heavy work (PepMLM, MetaLATTE) runs on a cloud machine instead of your laptop. You keep your computer free and can use more RAM/CPU or a GPU.

---

## Option 1: Google Colab (easiest, free tier)

Run the pipeline in a **notebook in the cloud**. No server to manage; you get a Linux machine with Python and (on paid) GPU.

**Steps:**

1. Put your project (or at least the code + seeds) in **Google Drive** or a **GitHub repo**.
2. Open [colab.research.google.com](https://colab.research.google.com), New Notebook.
3. Mount Drive (if your files are there) and install deps in the first cells:

```python
# Cell 1: Mount Drive (if project is in Drive)
from google.colab import drive
drive.mount("/content/drive")
%cd /content/drive/MyDrive/AML_Final_Project-master   # adjust path
```

```python
# Cell 2: Install (Colab has numpy/pandas; add the rest)
!pip install -q "numpy>=2"
!pip install -q torch transformers accelerate biopython streamlit
```

4. Run the pipeline from code (same logic as `pipeline_runner.run_pipeline`), or run the Streamlit app and use **ngrok** to get a public URL (see Colab docs). Simpler: skip Streamlit and call the runner:

```python
# Cell 3: Run pipeline (adjust paths to your seeds/output)
from pathlib import Path
from pipeline_runner import PipelineConfig, run_pipeline

cfg = PipelineConfig(
    seed_fasta=Path("PepMLM_seeds/MT_seeds/MT_seeds_test.txt"),
    work_dir=Path("cloud_run_1"),
    n_variants_per_seed=10,
    fraction_mask=0.10,
    topk_per_mask=5,
    max_len=400,
    top_k=20,
)
outputs = run_pipeline(cfg)
print(outputs)
```

5. **Download results** from Colab: right‑click `cloud_run_1/generated_variants.fasta` (and the CSV/PNG) in the file browser, or use `files.download()`.

**Caveat:** MetaLATTE in this repo expects **local** MetaLATTE + ESM2 dirs (strict offline). On Colab you’d need to either (a) download those models into the session (or mount from Drive), or (b) change the code to load MetaLATTE/ESM2 from Hugging Face so it works without local files. PepMLM already falls back to Hugging Face when `PepMLM_local` is missing.

**Colab limits (free):** ~12 GB RAM, session timeout; Pro gives more RAM and longer runtimes.

---

## Option 2: Cloud VM (full control, pay per hour)

Run your **exact** project (Streamlit app or `pipeline_run.py`) on a Linux VM. You get a fixed IP or URL and more resources.

**Typical choices:**

| Provider      | Product              | Notes                          |
|---------------|----------------------|--------------------------------|
| **Google Cloud**  | Compute Engine (e2-standard-4) | 4 vCPU, 16 GB RAM; ~\$0.13/h |
| **AWS**           | EC2 (e.g. t3.xlarge)  | 4 vCPU, 16 GB RAM; similar    |
| **Azure**         | Virtual Machine       | Same idea                      |
| **Lambda Labs**   | GPU/CPU cloud         | Good if you want a GPU later   |
| **RunPod**        | Pods                  | GPU-focused, pay per use       |

**Steps (same idea everywhere):**

1. Create a VM: **Ubuntu 22.04**, at least **8 GB RAM** (16 GB is comfortable), 2+ vCPUs.
2. SSH in and install Python 3.12, git, and your project:

```bash
sudo apt update && sudo apt install -y python3.12 python3.12-venv git
git clone https://github.com/YOUR_USER/AML.git
cd AML/AML_Final_Project-master
```

3. Create venv and install (same as local):

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install "numpy>=2"
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install streamlit pandas matplotlib transformers accelerate biopython
```

4. Run the app (bind to 0.0.0.0 so you can reach it):

```bash
.venv/bin/python -m streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
```

5. **Reach the UI:**
   - **Option A:** Open port 8501 in the cloud firewall and visit `http://<VM_PUBLIC_IP>:8501`.
   - **Option B:** Keep the port closed and use **SSH port forwarding** from your laptop:
     ```bash
     ssh -L 8501:localhost:8501 user@<VM_IP>
     ```
     Then on the VM run the Streamlit command above; on your laptop open http://localhost:8501.

**Optional GPU:** For a GPU VM, install CUDA and `pip install torch` (no `--index-url cpu`). Same Streamlit command; the pipeline will use the GPU.

---

## Option 3: Streamlit Community Cloud (hosted UI)

Run the **Streamlit app** in the cloud and get a public URL (e.g. `yourapp.streamlit.app`).

1. Push your repo to **GitHub** (with `streamlit_app.py`, `pipeline_runner.py`, etc., at the repo root or in a subfolder).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub, **New app**.
3. Pick the repo and branch; set **Main file path** to e.g. `streamlit_app.py` (or `AML_Final_Project-master/streamlit_app.py` if the app lives in that subfolder).
4. Set **Python version** to 3.12.
5. Deploy. The free tier has limited RAM; heavy runs (many variants, MetaLATTE) may need a paid tier or a different option.

**Note:** The current MetaLATTE script is strict-offline (local dirs only). For Streamlit Cloud you’d need to change it to load MetaLATTE/ESM2 from Hugging Face when local paths are missing, or the pipeline will fail at the MetaLATTE step.

---

## What to pick

- **Just want to run the pipeline a few times, no UI needed:** Colab (Option 1). Upload project or clone from GitHub, run `run_pipeline()` in a notebook, download outputs.
- **Want the full Streamlit UI in the cloud and control over machine size:** VM (Option 2). Use SSH port forwarding if you don’t want to open the port to the internet.
- **Want a public shareable UI with minimal setup:** Streamlit Community Cloud (Option 3); plan on adapting MetaLATTE to use Hugging Face or the deploy may run out of memory / fail on missing local models.

For “commission cloud so it doesn’t crash my computer,” **Option 2 (VM)** or **Option 1 (Colab)** are the most straightforward; Option 2 gives you the same experience as local but on a bigger machine.
