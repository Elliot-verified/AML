# Get the Streamlit app running locally

Follow these steps **in order** in a terminal. Use the **project venv** only (do not rely on Anaconda) so numpy/sklearn/streamlit all match.

---

## Step 1: Go to the project folder

```bash
cd /Users/elliotwaxman/Desktop/AML_Project/AML/AML_Final_Project-master
```

(Or wherever your `AML_Final_Project-master` folder lives.)

---

## Step 2: Create the venv and install everything

Run the setup script. It uses the venv’s own `pip`, so it doesn’t matter if Anaconda is in your PATH:

```bash
bash setup_venv.sh
```

Wait until it finishes (PyTorch can take a few minutes). If you see **“No space left on device”**, free some disk space, then run again.

---

## Step 3: Start the Streamlit app

Use **one** of these. Both use the venv’s Python so you don’t pick up Conda.

**Option A – launcher:**

```bash
bash run_app.sh
```

**Option B – direct (must run from inside AML_Final_Project-master):**

```bash
cd /Users/elliotwaxman/Desktop/AML_Project/AML/AML_Final_Project-master
.venv/bin/python -m streamlit run streamlit_app.py
```

Then open the URL shown (e.g. **http://localhost:8501**).

---

## Step 4: Run the pipeline in the UI

1. In the app, choose **“Use a predefined seed file”** and pick one (e.g. `PepMLM_seeds/MT_seeds/MT_seeds_test.txt`).
2. Set parameters (or leave defaults). Keep **Variants per seed** small (e.g. 5–10) for a quick test.
3. Click **“Run pipeline”**.

**What happens:**

- **PepMLM:** If you don’t have a `PepMLM_local` folder, the app will load **ChatterjeeLab/PepMLM-650M** from Hugging Face (first run will download ~2.3 GB).
- **MetaLATTE:** The script expects **local** MetaLATTE and ESM2 folders. If you don’t have them, the pipeline will fail at step 2 with a “missing” or “offline” error. To run the full pipeline you’ll need to add those model dirs (see RUN_NEXT.md). You can still confirm the UI and PepMLM step work without them.

---

## If something goes wrong

| Problem | What to do |
|--------|------------|
| `No module named streamlit` | Run **Step 2** again (`bash setup_venv.sh`). Ensure you then start the app with **Step 3** (don’t run `streamlit` from a conda-activated shell). |
| `numpy.dtype size changed` or `numpy.core.multiarray failed to import` | You’re still using Anaconda’s Python. Start the app **only** with `bash run_app.sh` or `.venv/bin/python -m streamlit run streamlit_app.py`. |
| `run_app.sh: command not found` / syntax error | Run the app with: `.venv/bin/python -m streamlit run streamlit_app.py` |
| No space left on device | Free disk space, remove `.venv`, then run `bash setup_venv.sh` again. Use CPU-only PyTorch (the script already does). |

---

## Quick checklist

1. `cd AML_Final_Project-master`
2. `bash setup_venv.sh` (wait until it finishes)
3. `bash run_app.sh` or `.venv/bin/python -m streamlit run streamlit_app.py`
4. Open http://localhost:8501, pick a seed file, click Run pipeline
