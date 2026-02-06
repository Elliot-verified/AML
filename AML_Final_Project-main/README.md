# AML_Final_Project

**After moving the project (e.g. from a zip), see [SETUP.md](SETUP.md) for step-by-step setup.**

### Installing Requirements

From the project root (`AML_Final_Project-main/`):

```bash
pip3 install -r requirements.txt
pip install torch transformers accelerate biopython
python parsing/parse_fasta.py stream.txt -o parsing/parsed_sequences.csv
```

pip install -U "transformers" "huggingface_hub[hf_transfer]" accelerate
export HF_HUB_ENABLE_HF_TRANSFER=1   # faster parallel downloads


## Pulling all of the FASTA Data in browser 
https://rest.uniprot.org/uniprotkb/stream?format=fasta&query=accession:P02795%20OR%20accession:P04732%20OR%20accession:P30331%20OR%20accession:P9WK09%20OR%20accession:P80294%20OR%20accession:P02794%20OR%20accession:P02792%20OR%20accession:P0A998%20OR%20accession:P0ABD3%20OR%20accession:P0ABT2%20OR%20accession:Q58AJ5%20OR%20accession:Q8XD09%20OR%20accession:P36649%20OR%20accession:Q99X86%20OR%20accession:P0A9M0%20OR%20accession:Q9HYJ1%20OR%20accession:P0A9E5%20OR%20accession:P55980%20OR%20accession:P12688


## 🧬 Project Goal

Design metal-binding proteins for bioremediation using machine learning (PepMLM + MetaLaTTE + AlphaFold).
Essentially, building a workflow to generate, rank, and validate protein sequences that could chelate heavy metals like Cu, Zn, Cd, or Fe.

## 🧠 Phase 1 – Set up data and model access

Defined the task: use ML (PepMLM, MetaLaTTE, AlphaFold 3) to design metal-binding proteins from seed sequences.

Curated seed proteins: built a balanced set of ~20 known binders (metallothioneins, ferritins, MerR-family regulators, etc.) using UniProt accessions.

Downloaded sequences: learned how to pull FASTA data from UniProt’s REST API directly.

Parsed and filtered data: wrote a parse_fasta.py script using Biopython to read and clean the FASTA records, add metadata, and prep for ML input.

## ⚙️ Phase 2 – Model environment

Set up virtual environment: installed transformers, torch, biopython, safetensors.

Resolved corporate SSL blocking: decided to bypass proxy certificate issues by running fully offline inside the venv.

Manually downloaded PepMLM checkpoint (≈ 2.3 GB) and tokenizer/config files into PepMLM_local/.

Loaded model successfully: confirmed model type = esm (Evolutionary Scale Model), which is a masked-language model.

## 🤖 Phase 3 – Running PepMLM

Validated single-mask prediction: used fill-mask pipeline to fill masked residues and confirm predictions.

Built a generation script: created pepmlm_generate.py to mask a fraction of residues, fill them sequentially, and generate variants.

Diagnosed slowness: initial script was CPU-heavy because it looped per mask.

Optimized: rewrote to pepmlm_generate_fast.py — vectorized, batched, fills all masks in one forward pass, skips long sequences, and adds progress logging.

Verified success: script now runs quickly on CPU (or MPS if available) and writes a FASTA of generated variants.

## 📊 Phase 4 – Next Steps (upcoming)

Filter candidates: length 50–500 aa, valid alphabet, desired cysteine count, minimal repeats.

Score with MetaLaTTE: predict metal-binding propensities (Cu, Zn, Cd, Fe).

Rank → select top candidates.

Structure prediction: feed the best 3–5 into AlphaFold 3 to confirm fold stability and metal pocket geometry.

(Optional) wet-lab synthesis / transformation into Deinococcus or E. coli.

## 💡 In summary

You now have a fully offline ML pipeline that:

Uses curated seed FASTA sequences

Generates new metal-binding protein variants with PepMLM

Produces ready-to-score FASTA outputs for downstream models

Essentially, you’ve built the data + model foundation for machine-learning-guided protein design — the hard infrastructure part is done ✅.