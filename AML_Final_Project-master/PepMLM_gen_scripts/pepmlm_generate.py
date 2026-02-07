# pepmlm_generate.py
import math, random, re
from typing import List, Set
from Bio import SeqIO
import torch
from transformers import AutoTokenizer, AutoModelForMaskedLM

MODEL_DIR = "PepMLM_local"
FASTA_IN  = "metal_binding_seeds.txt"     # change if needed
FASTA_OUT = "pepmlm_variants.fasta"

N_VARIANTS_PER_SEED = 10     # how many variants per input sequence
FRACTION_MASK       = 0.05   # % of positions masked per variant (0.05 = 5%)
TOPK_PER_MASK       = 1      # 1 = greedy; set to 5/10 for diversity per site

AA_ALLOWED = set("ACDEFGHIKLMNPQRSTVWY")

tok = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
mdl = AutoModelForMaskedLM.from_pretrained(MODEL_DIR, local_files_only=True)
device = "cuda" if torch.cuda.is_available() else "cpu"
mdl.to(device).eval()
MASK = tok.mask_token or "<mask>"

def clean_seq(s: str) -> str:
    s = s.strip().upper()
    s = re.sub(r"[^A-Z]", "", s)
    return "".join(ch if ch in AA_ALLOWED else "G" for ch in s)

@torch.no_grad()
def fill_leftmost_mask(text: str, topk=1) -> str:
    while MASK in text:
        enc = tok(text, return_tensors="pt").to(device)
        logits = mdl(**enc).logits[0]
        mask_idx = (enc["input_ids"][0] == tok.mask_token_id).nonzero(as_tuple=True)[0][0].item()
        probs = torch.softmax(logits[mask_idx], dim=-1)

        if topk <= 1:
            idx = torch.argmax(probs).item()
        else:
            topk_vals, topk_ids = torch.topk(probs, k=topk)
            topk_probs = topk_vals / topk_vals.sum()
            idx = topk_ids[torch.multinomial(topk_probs, 1)].item()

        tok_str = tok.convert_ids_to_tokens(idx).upper()
        aa = re.sub(r"[^A-Z]", "", tok_str)[:1] or "G"
        text = text.replace(MASK, aa, 1)
    return text

def choose_mask_positions(seq: str, n_mask: int, protect: Set[int]) -> List[int]:
    cand = [i for i in range(len(seq)) if i not in protect]
    n_mask = max(1, min(n_mask, len(cand)))
    return random.sample(cand, n_mask)

def generate_variants(seed_id: str, seed_seq: str) -> List[str]:
    seq = clean_seq(seed_seq)
    L = len(seq)
    n_mask = max(1, int(math.ceil(L * FRACTION_MASK)))
    protect = {i for i, aa in enumerate(seq) if aa == "C"}  # keep cysteines

    variants = []
    for k in range(N_VARIANTS_PER_SEED):
        pos = choose_mask_positions(seq, n_mask, protect)
        chars = list(seq)
        for i in pos:
            chars[i] = MASK
        masked = "".join(chars)
        filled = fill_leftmost_mask(masked, topk=TOPK_PER_MASK)
        variants.append(f">gen_{seed_id}_{k+1}\n{filled}\n")
    return variants

def main():
    out = []
    for rec in SeqIO.parse(FASTA_IN, "fasta"):
        sid = rec.id.replace("|", "_")
        out.extend(generate_variants(sid, str(rec.seq)))
    with open(FASTA_OUT, "w") as f:
        f.writelines(out)
    print(f"Wrote {len(out)} variants → {FASTA_OUT}")

if __name__ == "__main__":
    main()
