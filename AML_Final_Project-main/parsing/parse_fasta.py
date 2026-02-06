#!/usr/bin/env python3
import re
import argparse
import pandas as pd

def read_fasta(path):
    header = None
    seq_chunks = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header is not None:
                    yield header, "".join(seq_chunks)
                header = line
                seq_chunks = []
            else:
                seq_chunks.append(line)
    if header is not None:
        yield header, "".join(seq_chunks)

def parse_uniprot_header(header_line):
    """
    Parses UniProt FASTA headers like:
    >sp|P02792|FRIL_HUMAN Ferritin light chain OS=Homo sapiens OX=9606 GN=FTL PE=1 SV=2
    Returns a dict with db, accession, entry_name, protein_name, organism, taxon_id, gene, pe, sv
    """
    h = header_line.lstrip(">").strip()
    first, rest = (h.split(" ", 1) + [""])[:2]  # first token, then the rest
    # first looks like: sp|P02792|FRIL_HUMAN
    try:
        db, accession, entry_name = first.split("|", 2)
    except ValueError:
        db, accession, entry_name = (None, None, first)

    # protein name = everything up to OS= if present
    protein_name = rest.split(" OS=", 1)[0] if " OS=" in rest else rest

    # capture key=value pairs (OS, OX, GN, PE, SV); OS can contain spaces
    tags = dict(re.findall(r"(\b[A-Z]{2})=([^=]+?)(?=\s[A-Z]{2}=|$)", rest))
    return {
        "db": db,
        "accession": accession,
        "entry_name": entry_name,
        "protein_name": protein_name.strip() or None,
        "organism": tags.get("OS"),
        "taxon_id": tags.get("OX"),
        "gene": tags.get("GN"),
        "pe": tags.get("PE"),
        "sv": tags.get("SV"),
    }

def main(in_fasta, out_csv):
    rows = []
    for header, seq in read_fasta(in_fasta):
        meta = parse_uniprot_header(header)
        meta.update({
            "length": len(seq),
            "cysteines": seq.count("C"),
            "sequence": seq
        })
        rows.append(meta)
    df = pd.DataFrame(rows, columns=[
        "accession","entry_name","protein_name","organism","gene",
        "taxon_id","pe","sv","db","length","cysteines","sequence"
    ])
    df.to_csv(out_csv, index=False)
    print(f"Parsed {len(df)} sequences → {out_csv}")

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Parse UniProt FASTA to CSV")
    p.add_argument("fasta", help="Path to UniProt FASTA (.fasta or .txt)")
    p.add_argument("-o","--out", default="parsed_sequences.csv", help="Output CSV")
    args = p.parse_args()
    main(args.fasta, args.out)
