# pepmlm_generate_fast.py
import argparse
import math
import os
import random
import re
import sys
import time
from typing import List, Set, Tuple
from Bio import SeqIO
import torch
from transformers import AutoTokenizer, AutoModelForMaskedLM

# Project root = parent of gen_scripts/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _path(*parts: str) -> str:
    return os.path.join(_PROJECT_ROOT, *parts)

# Hugging Face model ID: no local download required; uses HF cache on first run
DEFAULT_HF_MODEL = "ChatterjeeLab/PepMLM-650M"
DEFAULT_MODEL_DIR = _path("PepMLM_local")
DEFAULT_FASTA_IN = _path("metal_binding_seeds.txt")
DEFAULT_FASTA_OUT = _path("pepmlm_variants.fasta")

# ---- Tuning knobs ----
N_VARIANTS_PER_SEED = 6       # lower first; raise after it works
FRACTION_MASK       = 0.05    # 5% of positions masked per variant
TOPK_PER_MASK       = 1       # 1 = greedy; 5–10 = more diversity
MAX_LEN             = 400     # skip long sequences to keep CPU fast
BATCH_SIZE          = 8       # number of variants evaluated per forward pass

AA_ALLOWED = set("ACDEFGHIKLMNPQRSTVWY")

def log(msg):
    ts = time.strftime("[%H:%M:%S]")
    print(ts, msg, flush=True)

# cleans up sequences to be upper case; subsitutes non-canonical amino acids to G using the AA_ALLOWED set
def clean_seq(s: str) -> str:
    s = s.strip().upper()
    s = re.sub(r"[^A-Z]", "", s)
    return "".join(ch if ch in AA_ALLOWED else "G" for ch in s)

# uses list comprehension to create a list of masking positions that excludes protected regions
# uses either one or the number of candidates in the sequence for masking to get n_mask
# returns a sample of positions where masking can occur 
def choose_mask_positions(seq: str, n_mask: int, protect: Set[int]) -> List[int]:
    """" uses list comprehension to create a list of masking positions that excludes protected regions
        uses either one or the number of candidates in the sequence for masking to get n_mask
        returns a sample of positions where masking can occur """
    cand = [i for i in range(len(seq)) if i not in protect]
    n_mask = max(1, min(n_mask, len(cand)))
    return random.sample(cand, n_mask)

def make_masked(seq: str, positions: List[int], mask_token: str) -> str:
    chars = list(seq)
    for i in positions:
        chars[i] = mask_token
    return "".join(chars)

def fill_masks_batch(tokenizer, model, masked_texts: List[str], topk: int) -> List[str]:
    """
    Fills ALL mask positions for each sequence in one forward pass (batched).
    """
    device = next(model.parameters()).device
    enc = tokenizer(masked_texts, return_tensors="pt", padding=True).to(device)
    with torch.inference_mode():
        logits = model(**enc).logits  # [B, T, V]
        probs  = torch.softmax(logits, dim=-1)

    mask_id = tokenizer.mask_token_id
    input_ids = enc["input_ids"]  # [B, T]

    filled_texts = []
    for b in range(input_ids.size(0)):
        ids = input_ids[b].clone()
        mask_positions = (ids == mask_id).nonzero(as_tuple=True)[0].tolist()
        for pos in mask_positions:
            p = probs[b, pos]  # [V]
            if topk <= 1:
                idx = int(torch.argmax(p).item())
            else:
                vals, idxs = torch.topk(p, k=min(topk, p.numel()))
                idx = int(idxs[torch.multinomial(vals / vals.sum(), 1)].item())
            ids[pos] = idx
        # decode and slice off special tokens
        text = tokenizer.decode(ids, skip_special_tokens=True)
        # keep only A–Z letters (tokenizers sometimes emit spaces)
        text = re.sub(r"[^A-Z]", "", text)
        filled_texts.append(text)
    return filled_texts

def generate_variants_for_seed(
    rec_id: str,
    seq: str,
    tokenizer,
    model,
    mask_token: str,
) -> List[str]:
    seq = clean_seq(seq)
    L = len(seq)
    if L > MAX_LEN:
        log(f"skip {rec_id}: length {L} > MAX_LEN {MAX_LEN}")
        return []

    n_mask = max(1, int(math.ceil(L * FRACTION_MASK)))
    protect = {i for i, aa in enumerate(seq) if aa == "C"}  # preserve Cys

    variants_out = []
    to_do = N_VARIANTS_PER_SEED
    while to_do > 0:
        batch = min(BATCH_SIZE, to_do)
        masked_batch = []
        for _ in range(batch):
            pos = choose_mask_positions(seq, n_mask, protect)
            masked_batch.append(make_masked(seq, pos, mask_token))
        filled = fill_masks_batch(tokenizer, model, masked_batch, TOPK_PER_MASK)
        for i, fseq in enumerate(filled, 1):
            variants_out.append(f">gen_{rec_id}_{N_VARIANTS_PER_SEED - to_do + i}\n{fseq}\n")
        to_do -= batch
    return variants_out

def main():
    p = argparse.ArgumentParser(description="Generate metal-binding protein variants with PepMLM")
    p.add_argument("--input", "-i", default=DEFAULT_FASTA_IN, help="Input FASTA of seed sequences")
    p.add_argument("--output", "-o", default=DEFAULT_FASTA_OUT, help="Output FASTA of variants")
    p.add_argument("--model", default=DEFAULT_HF_MODEL, help="Hugging Face model ID (used when no local dir)")
    p.add_argument("--model-dir", "-m", default=None, help="Local PepMLM checkpoint dir; if set and exists, use it instead of --model")
    args = p.parse_args()

    fasta_in = args.input if os.path.isabs(args.input) else _path(args.input)
    fasta_out = args.output if os.path.isabs(args.output) else _path(args.output)
    model_dir = (args.model_dir if os.path.isabs(args.model_dir) else _path(args.model_dir)) if args.model_dir else DEFAULT_MODEL_DIR

    if not os.path.isfile(fasta_in):
        log(f"error: input FASTA not found: {fasta_in}")
        sys.exit(1)

    use_local = os.path.isdir(model_dir)
    if use_local:
        log(f"loading model/tokenizer from local dir: {model_dir}")
        tok = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
        mdl = AutoModelForMaskedLM.from_pretrained(model_dir, local_files_only=True)
    else:
        hf_id = args.model
        log(f"loading model/tokenizer from Hugging Face: {hf_id} (first run may download ~2.3 GB)")
        tok = AutoTokenizer.from_pretrained(hf_id)
        mdl = AutoModelForMaskedLM.from_pretrained(hf_id)
    device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
    mdl.to(device).eval()
    torch.set_num_threads(max(1, min(4, torch.get_num_threads())))  # keep CPU sane
    log(f"device: {device}; threads: {torch.get_num_threads()}")
    mask_token = tok.mask_token or "<mask>"

    out_lines = []
    total = 0
    for rec in SeqIO.parse(fasta_in, "fasta"):
        rec_id = rec.id.replace("|", "_")
        log(f"seed {rec_id} (len {len(rec.seq)}) …")
        out_lines.extend(generate_variants_for_seed(rec_id, str(rec.seq), tok, mdl, mask_token))
        total += 1

    os.makedirs(os.path.dirname(fasta_out) or ".", exist_ok=True)
    with open(fasta_out, "w") as f:
        f.writelines(out_lines)
    log(f"done: wrote {len(out_lines)} variants from {total} seeds → {fasta_out}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("interrupted by user")
        sys.exit(130)
