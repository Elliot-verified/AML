#!/usr/bin/env python3
# MetaLATTE FASTA -> CSV (strict offline; no SSL ever)

import os, sys, csv, traceback
from pathlib import Path
from typing import Optional
import importlib.util, importlib.machinery
import lightning

# ========= PATHS: EDIT THESE IF NEEDED =========
FASTA = "PepMLM_Outputs/MT_pepmlm_variants_test_tuned_v1.fasta"
OUT   = "/workarea/AML_Final_Project/MetaLATTE_Outputs/metalatte_preds_novel_MT_v1.csv"

# MetaLATTE: folder with config.json + model.safetensors/bin + configuration.py + model.py
# ESM2: folder with config.json + vocab.txt + tokenizer_config.json + model.safetensors/bin
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent

if os.environ.get("METALATTE_MODEL_DIR"):
    MODEL_DIR = os.environ["METALATTE_MODEL_DIR"]
elif (_project_root / "MetaLATTE").exists():
    MODEL_DIR = str(_project_root / "MetaLATTE")
else:
    MODEL_DIR = "/workarea/AML_Final_Project/MetaLATTE"

if os.environ.get("ESM_DIR"):
    ESM_DIR = os.environ["ESM_DIR"]
elif (_project_root / "esm2_local" / "esm2_t33_650M_UR50D").exists():
    ESM_DIR = str(_project_root / "esm2_local" / "esm2_t33_650M_UR50D")
else:
    ESM_DIR = "/workarea/AML_Final_Project/esm2_local/esm2_t33_650M_UR50D"
# ==============================================

# ========= STRICT OFFLINE / LOCAL-ONLY =========
os.environ.setdefault("HF_HOME", "/workarea/AML_Final_Project/.hf")
os.environ.setdefault("TRANSFORMERS_CACHE", os.path.join(os.environ["HF_HOME"], "transformers"))
os.environ.setdefault("HF_HUB_CACHE", os.path.join(os.environ["HF_HOME"], "hub"))
os.environ.setdefault("TORCH_HOME", os.path.join(os.environ["HF_HOME"], "torch"))
os.environ.setdefault("XDG_CACHE_HOME", os.environ["HF_HOME"])
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_EVALUATE_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

def _raise_offline(*args, **kwargs):
    raise RuntimeError("Networking is disabled. All models/assets must exist locally.")

def _install_network_kill_switch():
    try:
        import requests
        requests.sessions.Session.request = _raise_offline
    except Exception:
        pass
    try:
        import urllib3
        urllib3.PoolManager.__init__ = _raise_offline
    except Exception:
        pass
    try:
        import socket as _socket
        _orig = _socket.socket
        class _NoNet(_orig):
            def __init__(self, *a, **k):
                family = a[0] if a else k.get("family", _socket.AF_INET)
                if family in (_socket.AF_INET, _socket.AF_INET6):
                    _raise_offline()
                super().__init__(*a, **k)
        _socket.socket = _NoNet  # type: ignore
        _socket.getaddrinfo = _raise_offline  # type: ignore
    except Exception:
        pass
    try:
        import huggingface_hub as hfh
        for name in ("snapshot_download", "hf_hub_download"):
            if hasattr(hfh, name):
                setattr(hfh, name, _raise_offline)
        if hasattr(hfh, "HfApi"):
            class _NoApi:
                def __init__(self, *a, **k): _raise_offline()
            hfh.HfApi = _NoApi
        if hasattr(hfh, "HfFileSystem"):
            class _NoFS:
                def __init__(self, *a, **k): _raise_offline()
            hfh.HfFileSystem = _NoFS
    except Exception:
        pass

_install_network_kill_switch()
# ========= END STRICT OFFLINE =========

def _need(dirpath: str, names):
    missing = [n for n in names if not (Path(dirpath) / n).exists()]
    if missing:
        sys.exit(f"[offline] {dirpath} missing: {', '.join(missing)}")

def _assert_local_paths():
    # ESM2: tokenizer (slow) + config + weights
    _need(ESM_DIR, ["tokenizer_config.json", "config.json", "vocab.txt"])
    if not any((Path(ESM_DIR)/f).exists() for f in ("model.safetensors", "pytorch_model.bin")):
        sys.exit(f"[offline] ESM2 weights not found in {ESM_DIR} (need model.safetensors or pytorch_model.bin)")
    # MetaLATTE: config + weights + local python (configuration.py/model.py expected)
    _need(MODEL_DIR, ["config.json"])
    if not any((Path(MODEL_DIR)/f).exists() for f in ("model.safetensors", "pytorch_model.bin")):
        sys.exit(f"[offline] MetaLATTE weights not found in {MODEL_DIR} (need model.safetensors or pytorch_model.bin)")

_assert_local_paths()

def read_fasta(fp):
    name, seq = None, []
    with open(fp) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            if line.startswith(">"):
                if name: yield name, "".join(seq)
                name, seq = line[1:].strip(), []
            else:
                seq.append(line)
    if name: yield name, "".join(seq)

# ====== DIRECT TRANSFORMERS LOADING (LOCAL ONLY) ======
from transformers import AutoTokenizer, AutoModel, AutoConfig
import torch

def _try_register_local_metalatte(code_dir: str) -> bool:
    """Import local MetaLATTE python and register custom classes for 'metalatte'."""
    if code_dir not in sys.path:
        sys.path.insert(0, code_dir)
    cfg_path = Path(code_dir) / "configuration.py"
    if cfg_path.exists():
        loader = importlib.machinery.SourceFileLoader("configuration", str(cfg_path))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        mod_cfg = importlib.util.module_from_spec(spec)
        loader.exec_module(mod_cfg)
        sys.modules["configuration"] = mod_cfg

    for mod_path in [
        Path(code_dir) / "model.py",
        Path(code_dir) / "metalatte.py",
        Path(code_dir) / "src" / "metalatte" / "__init__.py",
    ]:
        if not mod_path.exists():
            continue
        spec = importlib.util.spec_from_file_location("metalatte_local", str(mod_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore

        cfg_cls = getattr(mod, "MetaLATTEConfig", None)
        mdl_cls = getattr(mod, "MultitaskProteinModel", None)
        if (cfg_cls is None) or (mdl_cls is None):
            try:
                from transformers import PretrainedConfig, PreTrainedModel
                for name, obj in vars(mod).items():
                    if cfg_cls is None and isinstance(obj, type) and issubclass(obj, PretrainedConfig):
                        cfg_cls = obj
                    if mdl_cls is None and isinstance(obj, type) and issubclass(obj, PreTrainedModel):
                        mdl_cls = obj
            except Exception:
                pass

        if cfg_cls and mdl_cls:
            AutoConfig.register("metalatte", cfg_cls)
            AutoModel.register(cfg_cls, mdl_cls)
            return True
    return False

def load_model(device=None, max_len=1022):
    tokenizer = AutoTokenizer.from_pretrained(ESM_DIR, use_fast=False, local_files_only=True)

    # Load/resolve MetaLATTE config (offline)
    try:
        config = AutoConfig.from_pretrained(MODEL_DIR, trust_remote_code=True, local_files_only=True)
    except ValueError as e:
        if "metalatte" in str(e).lower():
            if not _try_register_local_metalatte(MODEL_DIR):
                raise RuntimeError(
                    "Offline load failed: could not find/register MetaLATTE classes locally.\n"
                    f"Ensure {MODEL_DIR} has configuration.py and model.py."
                )
            config = AutoConfig.from_pretrained(MODEL_DIR, trust_remote_code=False, local_files_only=True)
        else:
            raise

    # Point the base ESM to your local folder
    for k in ("esm_model_name", "esm_model_id", "esm_checkpoint", "base_model_name"):
        if hasattr(config, k):
            setattr(config, k, ESM_DIR)
    for k in ("esm_revision", "base_model_revision"):
        if hasattr(config, k):
            setattr(config, k, None)

    # Keep outputs simple
    for flag in ("output_hidden_states", "output_attentions"):
        if hasattr(config, flag):
            setattr(config, flag, False)
    if hasattr(config, "return_dict"):
        setattr(config, "return_dict", True)

    # Build the model from local module
    import importlib.util
    mod_path = Path(MODEL_DIR) / "model.py"
    spec = importlib.util.spec_from_file_location("metalatte_local_build", str(mod_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    cls = getattr(mod, "MultitaskProteinModel", None)
    if cls is None:
        raise RuntimeError("Could not find MultitaskProteinModel in MetaLATTE/model.py")
    model = cls(config)

    # Load finetuned weights
    import safetensors.torch as st
    weights_path = None
    for name in ("model.safetensors", "pytorch_model.bin"):
        p = os.path.join(MODEL_DIR, name)
        if os.path.isfile(p):
            weights_path = p
            break
    if weights_path is None:
        raise RuntimeError(f"No local MetaLATTE weights found in {MODEL_DIR}")

    if weights_path.endswith(".safetensors"):
        state_dict = st.load_file(weights_path, device="cpu")
    else:
        state_dict = torch.load(weights_path, map_location="cpu", weights_only=False)

    if isinstance(state_dict, dict) and "state_dict" in state_dict:
        state_dict = state_dict["state_dict"]

    def _strip_prefix(d, prefix):
        return {(k[len(prefix):] if k.startswith(prefix) else k): v for k, v in d.items()}

    for pref in ("module.", "model.", "net."):
        state_dict = _strip_prefix(state_dict, pref)

    missing, unexpected = model.load_state_dict(state_dict, strict=False)
    if unexpected:
        print(f"[warn] unexpected keys (ignored): {sorted(unexpected)[:10]}{'...' if len(unexpected)>10 else ''}")
    if missing:
        print(f"[warn] missing keys: {sorted(missing)[:10]}{'...' if len(missing)>10 else ''}")

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device).eval()
    return tokenizer, model, config, device, max_len

# --------- metal head selection ----------
def _pick_metal_logits(out):
    """Return a tensor shaped (B, 14|15) from model output `out`."""
    import torch

    # Helper to search recursively
    def _search(obj):
        if torch.is_tensor(obj) and obj.dim() >= 2 and obj.size(-1) in (14, 15):
            return obj
        if isinstance(obj, dict):
            for v in obj.values():
                got = _search(v)
                if got is not None:
                    return got
        if isinstance(obj, (list, tuple)):
            for v in obj:
                got = _search(v)
                if got is not None:
                    return got
        return None

    # Heuristics: common field names
    cand_keys = (
        "metal_logits", "metals", "metals_logits", "binding_logits",
        "logits_metal", "metal", "task_logits"
    )
    if isinstance(out, dict):
        for k in cand_keys:
            if k in out:
                v = out[k]
                if isinstance(v, dict):
                    for vv in v.values():
                        got = _search(vv)
                        if got is not None:
                            return got
                else:
                    got = _search(v)
                    if got is not None:
                        return got

    # Try attributes (ModelOutput)
    for attr in cand_keys:
        if hasattr(out, attr):
            v = getattr(out, attr)
            if isinstance(v, dict):
                for vv in v.values():
                    got = _search(vv)
                    if got is not None:
                        return got
            else:
                got = _search(v)
                if got is not None:
                    return got

    # Fallback: out.logits only if it matches 14/15
    if hasattr(out, "logits"):
        v = out.logits
        got = _search(v)
        if got is not None:
            return got

    # Last resort: scan everything
    got = _search(out)
    if got is not None:
        return got

    raise RuntimeError(
        "Could not find metal-binding logits (expected last dim 14 or 15). "
        "You may be reading ESM vocab logits instead."
    )

def run_batch(tokenizer, model, seqs, device, max_len=1022):
    import torch
    toks = tokenizer(
        seqs,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=max_len,
    )
    toks = {k: v.to(device) for k, v in toks.items()}

    model.eval()
    with torch.no_grad():
        out = model(**toks)

    logits = _pick_metal_logits(out)

    # If per-token (B, L, C), pool over tokens -> (B, C)
    if logits.dim() == 3:
        logits = logits.mean(dim=1)
    elif logits.dim() == 1:
        logits = logits.unsqueeze(0)

    probs = torch.sigmoid(logits).cpu().numpy()  # (B, C)
    return probs

# ------------- id2label utilities -------------
def _dense_from_id2label(d: dict, n_expected: Optional[int] = None):
    keys_int = {int(k) if not isinstance(k, int) else k for k in d.keys()}
    n = (max(keys_int) + 1) if n_expected is None else n_expected
    out = [None] * n
    for k, v in d.items():
        out[int(k)] = v
    return out

def _dense_from_label2id(d: dict, n_expected: Optional[int] = None):
    n = (max(int(v) for v in d.values()) + 1) if n_expected is None else n_expected
    out = [None] * n
    for lab, idx in d.items():
        out[int(idx)] = lab
    return out

def _resolve_labels(config, C: int):
    """Return a list of C labels aligned with logits; will drop Non-binding if needed."""
    id2label_list = None
    try:
        _id2label = getattr(config, "id2label", None)
        _label2id = getattr(config, "label2id", None)
        if isinstance(_id2label, dict) and len(_id2label) > 0:
            id2label_list = _dense_from_id2label(_id2label)
        elif isinstance(_label2id, dict) and len(_label2id) > 0:
            id2label_list = _dense_from_label2id(_label2id)
    except Exception:
        id2label_list = None

    # No config labels -> None (caller will use numeric names temporarily)
    if not id2label_list:
        return None

    # Exact match
    if len(id2label_list) == C:
        return id2label_list

    # Common case: config has Non-binding but head is metals-only
    drop_names = {"Non-binding", "non-binding", "None", "Background", "Negative"}
    filtered = [lab for lab in id2label_list if lab not in drop_names and lab is not None]
    if len(filtered) == C:
        return filtered

    # Last resort: truncate/pad (but preserve order for as many as possible)
    print(f"[warn] id2label length {len(id2label_list)} != logits {C}; truncating")
    return (id2label_list[:C] + [str(i) for i in range(C)])[0:C]

# --------------------- main workhorse ---------------------
def run_metalatte_on_fasta(
    fasta_path: str,
    out_csv_path: str,
) -> str:
    """
    Run MetaLATTE on a FASTA file and write predictions to CSV.

    Parameters
    ----------
    fasta_path : str
        Path to the input FASTA file with sequences.
    out_csv_path : str
        Path where the CSV with probabilities will be written.

    Returns
    -------
    str
        The path to the written CSV (out_csv_path).
    """
    # make sure output directory exists
    os.makedirs(os.path.dirname(out_csv_path), exist_ok=True)

    # load model/tokenizer once
    tokenizer, model, config, device, max_len = load_model()

    # read sequences
    records = list(read_fasta(fasta_path))
    if not records:
        sys.exit(f"No sequences found in {fasta_path}")

    BATCH = 8
    rows = []

    for i in range(0, len(records), BATCH):
        batch = records[i:i+BATCH]
        ids   = [h for (h, s) in batch]
        seqs  = [s for (h, s) in batch]

        try:
            probs = run_batch(tokenizer, model, seqs, device, max_len=max_len)  # (B, C)
        except RuntimeError as e:
            print(f"[offline-block] batch starting {ids[0]}: {e}")
            traceback.print_exc(limit=1)
            continue

        C = probs.shape[1]
        labels = _resolve_labels(config, C)

        for j, sid in enumerate(ids):
            row = {"id": sid, "sequence": seqs[j]}
            vec = probs[j].tolist()
            if labels:
                for k, lab in enumerate(labels):
                    safe = lab if (lab is not None and lab != "") else str(k)
                    row[f"prob_{safe}"] = float(vec[k])
            else:
                for k, val in enumerate(vec):
                    row[f"prob_{k}"] = float(val)
            rows.append(row)

    if not rows:
        raise RuntimeError(
            "No rows produced. Likely missing/invalid local model assets. "
            "Check paths and try again."
        )

    # Drop numeric fallback columns (if any slipped through)
    for row in rows:
        for k in list(row.keys()):
            if k.startswith("prob_") and k[5:].isdigit():
                row.pop(k, None)

    # Build final field order: id, sequence, then sorted prob_* columns
    prob_cols = sorted({
        k
        for r in rows
        for k in r.keys()
        if k.startswith("prob_") and not k[5:].isdigit()
    })
    fieldnames = ["id", "sequence"] + prob_cols

    with open(out_csv_path, "w", newline="") as wf:
        writer = csv.DictWriter(wf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("✓ wrote", out_csv_path)
    return out_csv_path


def main():
    """
    CLI entrypoint.

    Usage:
        python run_metalatte_fasta.py [FASTA_IN] [OUT_CSV]

    If arguments are omitted, uses the module-level FASTA and OUT defaults.
    """
    fasta = FASTA
    out_csv = OUT

    if len(sys.argv) >= 2:
        fasta = sys.argv[1]
    if len(sys.argv) >= 3:
        out_csv = sys.argv[2]

    run_metalatte_on_fasta(fasta, out_csv)

if __name__ == "__main__":
    main()
