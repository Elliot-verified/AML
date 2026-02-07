# What to do next to run the app

Follow these steps in order.

---

## Step 1: Free disk space (if you hit “No space left on device”)

```bash
cd AML_Final_Project-master
rm -rf .venv
pip cache purge
```

Delete other large files or old virtual envs if you need more space.

---

## Step 2: Create a venv and install (lite = CPU-only, smaller install)

```bash
cd AML_Final_Project-master
python3 -m venv .venv
source .venv/bin/activate
# Windows:  .venv\Scripts\activate

pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-web-lite.txt
```

If you have plenty of disk and want GPU support, use `pip install torch` (no `--index-url`) and `pip install -r requirements-web.txt` instead.

---

## Step 3: Launch the web app

```bash
cd AML_Final_Project-master
source .venv/bin/activate
streamlit run streamlit_app.py
```

Open the URL shown (e.g. **http://localhost:8501**). You’ll see the form to choose seeds and set parameters.

---

## Step 4: Run the full pipeline (PepMLM → MetaLATTE)

To actually **run the pipeline** when you click the button:

1. **PepMLM**  
   - If you have a **`PepMLM_local`** folder in the project root (with `config.json`, tokenizer, weights), it will be used.  
   - If not, the app will **load PepMLM from Hugging Face** (`ChatterjeeLab/PepMLM-650M`) on first run (downloads ~2.3 GB once; then uses cache). You need internet for the first run.

2. **MetaLATTE + ESM2**  
   Either:

   - **Option A:** Put model folders in the project:
     - `AML_Final_Project-master/MetaLATTE/` (MetaLATTE config + weights)
     - `AML_Final_Project-master/esm2_local/esm2_t33_650M_UR50D/` (ESM2)
   - **Option B:** Set env vars before running Streamlit:
     ```bash
     export METALATTE_MODEL_DIR=/path/to/your/MetaLATTE
     export ESM_DIR=/path/to/your/esm2_t33_650M_UR50D
     streamlit run streamlit_app.py
     ```

If these aren’t set up, the app still opens and you can change parameters; when you click **Run pipeline** you’ll get an error until PepMLM (and for the MetaLATTE step, MetaLATTE + ESM2) are available.

---

## Quick reference

| Goal                         | Command / requirement |
|-----------------------------|------------------------|
| Open the UI only            | Steps 1–3 (no models required) |
| Run full pipeline           | Step 4: add `PepMLM_local`, MetaLATTE, and ESM2 |
| Use a different MetaLATTE/ESM2 path | `export METALATTE_MODEL_DIR=... ESM_DIR=...` then run streamlit |
