# pepmlm_generate_fast.py
# Heavy imports (torch, transformers, Bio) are inside run_pepmlm() so the app
# can load without pulling in sklearn/numpy from transformers.
import math
import random
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Set

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_DIR = _PROJECT_ROOT / "PepMLM_local"
HF_MODEL_ID = "ChatterjeeLab/PepMLM-650M"

AA_ALLOWED = set("ACDEFGHIKLMNPQRSTVWY")

@dataclass
class PepMLMConfig:
    fasta_in: Path
    fasta_out: Path
    n_variants_per_seed: int = 10
    fraction_mask: float = 0.10
    topk_per_mask: int = 5
    max_len: int = 400
    batch_size: int = 8

def log(msg):
    ts = time.strftime("[%H:%M:%S]")
    print(ts, msg, flush=True)

def clean_seq(s: str) -> str:
    s = s.strip().upper()
    s = re.sub(r"[^A-Z]", "", s)
    return "".join(ch if ch in AA_ALLOWED else "G" for ch in s)

def choose_mask_positions(seq: str, n_mask: int, protect: Set[int]) -> List[int]:
    cand = [i for i in range(len(seq)) if i not in protect]
    n_mask = max(1, min(n_mask, len(cand)))
    return random.sample(cand, n_mask)

def make_masked(seq: str, positions: List[int], mask_token: str) -> str:
    chars = list(seq)
    for i in positions:
        chars[i] = mask_token
    return "".join(chars)

def fill_masks_batch(tokenizer, model, masked_texts: List[str], topk: int) -> List[str]:
    import torch
    device = next(model.parameters()).device
    enc = tokenizer(masked_texts, return_tensors="pt", padding=True).to(device)
    with torch.inference_mode():
        logits = model(**enc).logits
        probs  = torch.softmax(logits, dim=-1)

    mask_id = tokenizer.mask_token_id
    input_ids = enc["input_ids"]

    filled_texts = []
    for b in range(input_ids.size(0)):
        ids = input_ids[b].clone()
        mask_positions = (ids == mask_id).nonzero(as_tuple=True)[0].tolist()
        for pos in mask_positions:
            p = probs[b, pos]
            if topk <= 1:
                idx = int(torch.argmax(p).item())
            else:
                vals, idxs = torch.topk(p, k=min(topk, p.numel()))
                idx = int(idxs[torch.multinomial(vals / vals.sum(), 1)].item())
            ids[pos] = idx
        text = tokenizer.decode(ids, skip_special_tokens=True)
        text = re.sub(r"[^A-Z]", "", text)
        filled_texts.append(text)
    return filled_texts

def generate_variants_for_seed(
    rec_id: str,
    seq: str,
    tokenizer,
    model,
    mask_token: str,
    cfg: PepMLMConfig,
) -> List[str]:
    seq = clean_seq(seq)
    L = len(seq)
    if L > cfg.max_len:
        log(f"skip {rec_id}: length {L} > MAX_LEN {cfg.max_len}")
        return []

    n_mask = max(1, int(math.ceil(L * cfg.fraction_mask)))
    protect = {i for i, aa in enumerate(seq) if aa == "C"}  # preserve Cys

    variants_out = []
    to_do = cfg.n_variants_per_seed
    while to_do > 0:
        batch = min(cfg.batch_size, to_do)
        masked_batch = []
        for _ in range(batch):
            pos = choose_mask_positions(seq, n_mask, protect)
            masked_batch.append(make_masked(seq, pos, mask_token))
        filled = fill_masks_batch(tokenizer, model, masked_batch, cfg.topk_per_mask)
        for i, fseq in enumerate(filled, 1):
            idx = cfg.n_variants_per_seed - to_do + i
            variants_out.append(f">gen_{rec_id}_{idx}\n{fseq}\n")
        to_do -= batch
    return variants_out

def run_pepmlm(cfg: PepMLMConfig) -> None:
    from Bio import SeqIO
    import torch
    from transformers import AutoTokenizer, AutoModelForMaskedLM

    use_local = DEFAULT_MODEL_DIR.is_dir() and (DEFAULT_MODEL_DIR / "config.json").exists()
    if use_local:
        log("loading PepMLM model/tokenizer from local dir…")
        tok = AutoTokenizer.from_pretrained(str(DEFAULT_MODEL_DIR), local_files_only=True)
        mdl = AutoModelForMaskedLM.from_pretrained(str(DEFAULT_MODEL_DIR), local_files_only=True)
    else:
        log(f"loading PepMLM from Hugging Face ({HF_MODEL_ID}); first run may download ~2.3 GB")
        tok = AutoTokenizer.from_pretrained(HF_MODEL_ID)
        mdl = AutoModelForMaskedLM.from_pretrained(HF_MODEL_ID)

    device = "cuda" if torch.cuda.is_available() else (
        "mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else "cpu"
    )
    mdl.to(device).eval()
    torch.set_num_threads(max(1, min(4, torch.get_num_threads())))
    log(f"device: {device}; threads: {torch.get_num_threads()}")
    mask_token = tok.mask_token or "<mask>"

    out_lines = []
    total = 0
    for rec in SeqIO.parse(str(cfg.fasta_in), "fasta"):
        rec_id = rec.id.replace("|", "_")
        log(f"seed {rec_id} (len {len(rec.seq)}) …")
        out_lines.extend(
            generate_variants_for_seed(
                rec_id, str(rec.seq), tok, mdl, mask_token, cfg
            )
        )
        total += 1

    cfg.fasta_out.parent.mkdir(parents=True, exist_ok=True)
    with open(cfg.fasta_out, "w") as f:
        f.writelines(out_lines)
    log(f"done: wrote {len(out_lines)} variants from {total} seeds → {cfg.fasta_out}")

def main():
    # keep your original behavior for backwards compatibility
    cfg = PepMLMConfig(
        fasta_in=Path("PepMLM_seeds/MT_seeds/MT_seeds_test.txt"),
        fasta_out=Path("PepMLM_Outputs/MT_pepmlm_variants_test_tuned_v2.fasta"),
    )
    run_pepmlm(cfg)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("interrupted by user")
        sys.exit(130)
