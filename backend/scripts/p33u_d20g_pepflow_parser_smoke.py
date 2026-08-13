#!/usr/bin/env python3
"""P33U D20G PepFlow parser/artifact smoke.

Read-only parse of an existing PepFlow real-run output (case0.pt) to confirm
interpretability of decoded outputs. Does NOT run the model forward pass and
does NOT generate new candidates. Honest artifact_only_parser_smoke.

Rationale: PepFlowAdapter.submit() is unconditionally blocked (read-only
skeleton). The console therefore exposes a parser smoke on the existing D7
real-run artifact (case0.pt, produced by run p33u_pepflow_579c0bfffcab41f1,
exit 0, GPU1, model2.pt). This confirms tensor structure + decoded token
indices are interpretable, without faking a new forward pass or new sequences.
"""
import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case0", required=True, help="path to case0.pt")
    ap.add_argument("--provenance", default="", help="optional provenance.json for the source run")
    ap.add_argument("--out", required=True, help="output JSON path")
    args = ap.parse_args()

    import torch  # local import: only PepFlow env has torch at this path

    case0 = Path(args.case0)
    if not case0.is_file():
        raise FileNotFoundError(f"case0.pt not found: {case0}")
    sha = hashlib.sha256(case0.read_bytes()).hexdigest()
    obj = torch.load(case0, map_location="cpu", weights_only=False)

    shapes: dict = {}
    for k, v in obj.items():
        if hasattr(v, "shape"):
            shapes[k] = {"type": "Tensor", "shape": list(v.shape), "dtype": str(v.dtype)}
        elif isinstance(v, dict):
            shapes[k] = {"type": "dict", "keys": list(v.keys())[:20]}
        else:
            shapes[k] = {"type": type(v).__name__}

    decoded: dict = {}
    # seqs: (N, L) integer token indices. We record RAW indices only.
    # AA-vocab mapping is NOT asserted here: PepFlow's internal token id order
    # is not staged in console scope, so mapping indices to a specific AA
    # alphabet would risk fabricating a sequence. Honest: record indices.
    if "seqs" in obj and hasattr(obj["seqs"], "tolist"):
        seqs_t = obj["seqs"]
        decoded["seqs_shape"] = list(seqs_t.shape)
        decoded["seqs_raw_token_indices"] = [list(map(int, row)) for row in seqs_t.tolist()]
        decoded["seqs_value_range"] = {
            "min": int(seqs_t.min().item()),
            "max": int(seqs_t.max().item()),
        }
        decoded["note"] = (
            "Raw PepFlow token indices recorded. AA-alphabet mapping NOT asserted "
            "(vocab file not staged); indices confirm discrete per-residue tokens exist."
        )
    if "seqs_simplex" in obj and hasattr(obj["seqs_simplex"], "shape"):
        decoded["seqs_simplex_shape"] = list(obj["seqs_simplex"].shape)
    if "rotmats" in obj and hasattr(obj["rotmats"], "shape"):
        decoded["rotmats_shape"] = list(obj["rotmats"].shape)
        decoded["structure_frames_interpretable"] = True
    if "trans" in obj and hasattr(obj["trans"], "shape"):
        decoded["trans_shape"] = list(obj["trans"].shape)
    if "angles" in obj and hasattr(obj["angles"], "shape"):
        decoded["angles_shape"] = list(obj["angles"].shape)

    result = {
        "smoke_type": "pepflow_artifact_parser_smoke",
        "case0_path": str(case0),
        "case0_sha256": sha,
        "tensor_keys": sorted(obj.keys()) if isinstance(obj, dict) else [],
        "tensor_shapes": shapes,
        "decoded": decoded,
        "interpretability": "OK" if decoded else "NO_DECODED_FIELDS",
        "ran_model_forward": False,
        "generated_new_candidates": False,
        "faked_sequence_or_structure": False,
        "prediction_tag": "COMPUTATIONAL_PREDICTION_ONLY",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
    }
    if args.provenance and Path(args.provenance).is_file():
        try:
            result["source_provenance"] = json.loads(Path(args.provenance).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            result["source_provenance"] = {"error": "could not read provenance"}

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": "OK", "out": str(out), "sha256": sha}, sort_keys=True))


if __name__ == "__main__":
    main()
