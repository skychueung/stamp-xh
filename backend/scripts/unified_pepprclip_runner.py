#!/usr/bin/env python3
"""Run the official PepPrCLIP MiniCLIP checkpoint over its peptide library."""

from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path


AA = set("ACDEFGHIKLMNPQRSTVWY")


def _clean_sequence(value: object) -> str:
    sequence = str(value or "").strip().upper()
    if not sequence or set(sequence) - AA:
        raise ValueError("target_sequence contains unsupported residues")
    return sequence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-json", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--result-json", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--candidate-library", required=True, type=Path)
    args = parser.parse_args()

    import esm
    import torch
    import torch.nn as nn
    import torch.nn.functional as functional

    class MiniCLIP(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.pep_embedder = nn.Sequential(nn.Linear(1280, 640), nn.ReLU(), nn.Linear(640, 320))
            self.prot_embedder = nn.Sequential(nn.Linear(1280, 640), nn.ReLU(), nn.Linear(640, 320))

    payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    target = _clean_sequence(payload.get("target_sequence"))
    length = int(payload.get("peptide_length", 12))
    count = max(1, int(payload.get("num_candidates", 5)))
    requested_device = str(payload.get("device", "cuda"))
    device = torch.device("cuda" if requested_device != "cpu" and torch.cuda.is_available() else "cpu")
    if not args.checkpoint.is_file():
        raise FileNotFoundError(f"PepPrCLIP checkpoint missing: {args.checkpoint}")
    if not args.candidate_library.is_file():
        raise FileNotFoundError(f"PepPrCLIP candidate library missing: {args.candidate_library}")

    esm_model, alphabet = esm.pretrained.esm2_t33_650M_UR50D()
    esm_model = esm_model.to(device).eval()
    converter = alphabet.get_batch_converter()
    _, _, tokens = converter([("target", target)])
    tokens = tokens.to(device)
    with torch.inference_mode():
        representation = esm_model(tokens, repr_layers=[33], return_contacts=False)["representations"][33]
        target_embedding = representation[0, 1:-1].mean(0)

    checkpoint = torch.load(args.checkpoint, map_location="cpu")
    state = checkpoint.get("state_dict", checkpoint)
    state = {key.removeprefix("model."): value for key, value in state.items()}
    miniclip = MiniCLIP()
    miniclip.load_state_dict(state, strict=True)
    miniclip = miniclip.to(device).eval()

    with args.candidate_library.open("rb") as handle:
        library = pickle.load(handle)
    selected = [(str(seq), embedding) for seq, embedding in library.items() if len(str(seq)) == length]
    if not selected:
        raise ValueError(f"candidate library has no peptides of length {length}")

    prot = functional.normalize(miniclip.prot_embedder(target_embedding.unsqueeze(0)), dim=-1)
    scored: list[tuple[float, str]] = []
    batch_size = max(1, int(payload.get("pepprclip_batch_size", 4096)))
    with torch.inference_mode():
        for start in range(0, len(selected), batch_size):
            rows = selected[start:start + batch_size]
            embeddings = torch.stack([torch.as_tensor(item[1]) for item in rows]).to(device)
            peptide = functional.normalize(miniclip.pep_embedder(embeddings), dim=-1)
            scores = (peptide @ prot.T).squeeze(1).detach().cpu().tolist()
            scored.extend((float(score), sequence) for score, (sequence, _) in zip(scores, rows))
    scored.sort(reverse=True)
    candidates = [
        {"candidate_id": f"pepprclip_{rank:04d}", "sequence": sequence,
         "rank": rank, "score": score, "clip_score": score}
        for rank, (score, sequence) in enumerate(scored[:count], 1)
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.result_json.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "candidates": candidates,
        "metrics": {"library_size": len(library), "eligible_peptides": len(selected), "device": str(device)},
        "warnings": ["Computational predictions; validation_status=NOT_EXPERIMENTALLY_VALIDATED"],
    }
    args.result_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
