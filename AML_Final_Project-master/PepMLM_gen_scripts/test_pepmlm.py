from transformers import AutoTokenizer, AutoModelForMaskedLM, pipeline

MODEL_DIR = "PepMLM_local"   # your local folder with config + weights

# Load tokenizer/model entirely offline
tok = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
mdl = AutoModelForMaskedLM.from_pretrained(MODEL_DIR, local_files_only=True)

print("Loaded OK. Model type:", getattr(mdl.config, "model_type", "?"))
print("Mask token:", tok.mask_token)

# Quick sanity check: fill a single mask in a toy peptide
seq = "MDPNCSCAAGDSCTCAGSCK"   # e.g., a metallothionein fragment
masked = seq[:10] + tok.mask_token + seq[11:]
fill = pipeline("fill-mask", model=mdl, tokenizer=tok, top_k=5)
print("Masked input:", masked)
print("Predictions:", fill(masked))
