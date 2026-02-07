#!/usr/bin/env python3
import importlib.util, sys, os
import argparse 

mod_path = "/workarea/AML_Final_Project/MetaLATTE/model.py"
spec = importlib.util.spec_from_file_location("metalatte_model", mod_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def read_fasta(fp):
    name, seq = None, []
    with open(fp) as f:
        for line in f:
            line=line.strip()
            if not line: continue
            if line.startswith(">"):
                if name: yield name, "".join(seq)
                name, seq = line[1:].strip(), []
            else:
                seq.append(line)
        if name: yield name, "".join(seq)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fasta", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--model_dir", default="MetaLATTE/model")
    p.add_argument("--esm_dir", default="esm2_local/esm2_t33_650M_UR50D")
    args = p.parse_args()

    # Try imports in both layouts
    pkg = None
    try:
        import metalatte as pkg  # if you mapped model/ -> metalatte in setup.py
    except Exception:
        sys.path.append(os.path.abspath("MetaLATTE"))
        import model as pkg  # original layout

    # Try to resolve a predict function
    predict_fn = None
    for cand in ("predict_proba", "predict", "inference", "infer"):
        if hasattr(pkg, cand):
            predict_fn = getattr(pkg, cand)
            break
    # Or a loader + method pattern
    model_obj = None
    if predict_fn is None:
        for loader in ("load_model", "from_pretrained", "load"):
            if hasattr(pkg, loader):
                model_obj = getattr(pkg, loader)(args.model_dir)
                break
        if model_obj is not None:
            for cand in ("predict_proba", "predict"):
                if hasattr(model_obj, cand):
                    predict_fn = getattr(model_obj, cand)
                    break

    if predict_fn is None:
        raise RuntimeError(
            "Could not find a predict function. Open MetaLATTE/model/model.py and look for "
            "a callable like predict()/predict_proba() or a class with that method, then edit this script."
        )

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="") as wf:
        writer = None
        for name, seq in read_fasta(args.fasta):
            # Call patterns to try; customize as needed:
            try:
                res = predict_fn([seq])  # many repos accept a list of sequences
            except TypeError:
                res = predict_fn(seq)    # or a single sequence

            # Normalize result into {class: prob} dict
            if isinstance(res, dict): 
                probs = res
            elif isinstance(res, (list, tuple)) and res and isinstance(res[0], dict):
                probs = res[0]
            else:
                # last resort: assume iterable of probs with fixed labels
                labels = ["Zn","Cu","Fe","Mn","Mg","Ca","Co","Ni","Other"]
                probs = {labels[i]: float(res[i]) for i in range(min(len(labels), len(res)))}

            if writer is None:
                writer = csv.DictWriter(wf, fieldnames=["id","sequence"] + list(probs.keys()))
                writer.writeheader()
            row = {"id": name, "sequence": seq, **probs}
            writer.writerow(row)
    print(f"✓ wrote {args.out}")

if __name__ == "__main__":
    main()
