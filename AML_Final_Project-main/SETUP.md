# Getting the project working after moving (e.g. from a zip)

Run all commands from the **project root**: `AML_Final_Project-main/`.

---

## 1. Python environment

Create and use a virtual environment (recommended):

```bash
cd AML_Final_Project-main
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

---

## 2. Install dependencies

The project needs both the repo’s `requirements.txt` and ML packages:

```bash
pip install -r requirements.txt
pip install torch transformers accelerate biopython
```

Optional (faster Hugging Face downloads):

```bash
pip install -U "transformers" "huggingface_hub[hf_transfer]" accelerate
export HF_HUB_ENABLE_HF_TRANSFER=1
```

---

## 3. Parsing FASTA (optional if you already have `parsed_sequences.csv`)

From project root:

```bash
python parsing/parse_fasta.py stream.txt -o parsing/parsed_sequences.csv
```

If you run from inside `parsing/`, use:

```bash
cd parsing
python parse_fasta.py ../stream.txt -o parsed_sequences.csv
```

---

## 4. PepMLM model (optional – use Hugging Face by default)

You **do not** need a local PepMLM folder. The script loads **ChatterjeeLab/PepMLM-650M** from Hugging Face by default. On first run it will download and cache the model (~2.3 GB) in `~/.cache/huggingface/`; later runs use the cache.

- **Default (recommended):** Just run the generator. It will use the Hugging Face model.
  ```bash
  python gen_scripts/pepmlm_generate_fast.py --input stream.txt
  ```
- **Offline / local:** If you have a local checkpoint, put it in the project root as **`PepMLM_local`** (or pass `--model-dir /path/to/it`). If that path exists, the script uses it instead of Hugging Face.
- **Different HF model:** Use `--model AnotherOrg/PepMLM-650M` to load a different Hugging Face model.

---

## 5. Seed FASTA for generation

`pepmlm_generate_fast.py` reads a FASTA of seed sequences. You can use the same file you used for parsing (e.g. `stream.txt`):

```bash
python gen_scripts/pepmlm_generate_fast.py --input stream.txt --output pepmlm_variants.fasta
```

If you don’t pass `--input`, the script looks for **`metal_binding_seeds.txt`** in the project root. So either:

- Pass `--input stream.txt` (or another FASTA), or  
- Copy/symlink your seed FASTA to `metal_binding_seeds.txt` in the project root.

---

## 6. MetaLATTE (scoring)

MetaLATTE code is in the repo; **model weights and one figure are not** (they were LFS and not in the zip). Download from Hugging Face and place in `MetaLATTE/`: `pytorch_model.bin`, `model/stage1_model.bin`, and optionally `figures/updated_front_page.png` from [ChatterjeeLab/MetaLATTE](https://huggingface.co/ChatterjeeLab/MetaLATTE). It uses ESM-2. From Python:

```python
# Run from project root or add it to sys.path
import sys
sys.path.insert(0, "MetaLATTE")
from transformers import AutoTokenizer, AutoModel, AutoConfig
from metalatte import MetaLATTEConfig, MultitaskProteinModel

AutoConfig.register("metalatte", MetaLATTEConfig)
AutoModel.register(MetaLATTEConfig, MultitaskProteinModel)

tokenizer = AutoTokenizer.from_pretrained("facebook/esm2_t33_650M_UR50D")
config = AutoConfig.from_pretrained("./MetaLATTE")
model = AutoModel.from_pretrained("./MetaLATTE", config=config)
# ... then run prediction on your sequences
```

If you run offline, you may need to download ESM-2 once (or use a local ESM-2 path).

---

## Quick checklist

| Step | What | Done? |
|------|------|-------|
| 1 | Create venv and activate | |
| 2 | `pip install -r requirements.txt` + `pip install torch transformers accelerate biopython` | |
| 3 | (Optional) Run `parsing/parse_fasta.py` if you need fresh `parsed_sequences.csv` | |
| 4 | (Optional) Add **PepMLM_local/** only if you want offline use; otherwise HF is used | |
| 5 | Run generator, e.g. `python gen_scripts/pepmlm_generate_fast.py --input stream.txt` | |

All paths in the scripts are relative to **project root** (`AML_Final_Project-main/`).
