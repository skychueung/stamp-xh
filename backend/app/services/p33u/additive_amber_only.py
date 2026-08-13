"""P33U-D4R additive: DiffPepBuilder Amber-only contract override.

ADDITIVE to the frozen P33U package. Does NOT modify ``runner_contracts.py``
(its SHA ``d9ce8ac6e0502a9e89840cfee371cfe69237d39b7d33586a285a6bb9c2f74e5b``
stays frozen). Provides an alternative DiffPepBuilder contract whose step-3
postprocess invokes ``experiments/amber_only_postprocess.py`` (Amber-only,
openmm) instead of ``experiments/run_postprocess.py`` with
``--amber_relax --rosetta_relax`` (which requires PyRosetta — unlicensed and
not installed in ``diffpepbuilder_py39``).

Design
------
- The frozen ``runner_contracts.get_contract('diffpepbuilder')`` still returns
  the original ``DiffPepBuilderContract`` (rosetta step-3). This additive
  module does NOT touch that registry.
- The Amber-only variant is obtained via ``get_contract_amber_only``. Binding
  it to ``runner.execute_run`` makes the real spawn use the Amber-only script,
  because ``execute_run`` calls ``contract.command_preview`` to build the
  command (verified by ``test_p33u_amber_only_zero_model.py``).
- Only ``command_preview`` step-3 is overridden. ``validate_input``,
  ``expected_artifacts``, ``verify_assets``, ``parse_output``, and
  ``execute`` are inherited unchanged from the frozen contract.

Command contract (step 3)::

    [<env_python>, <source>/experiments/amber_only_postprocess.py,
     --in_pdbs, <source>/runs/inference,
     --ori_pdbs, <input_dir>,
     --lig_chain_id, A]

Forbidden tokens in step 3 (asserted by tests):
    - ``run_postprocess.py``
    - ``--rosetta_relax``
    - ``pyrosetta``

Rosetta ddG: stays ``unavailable_with_reason`` — see
``amber_only_postprocess.ROSETTA_DDG_STATUS``.
"""

from __future__ import annotations

import os
from typing import Any

from .runner_contracts import DiffPepBuilderContract


# Re-exported so callers/tests can assert the rosetta-ddg unavailable reason
# without importing the DiffPepBuilder source script.
ROSETTA_DDG_UNAVAILABLE_REASON = (
    "unavailable_with_reason: rosetta_ddg_not_run_pyrosetta_licensed_out_of_scope"
)


class DiffPepBuilderAmberOnlyContract(DiffPepBuilderContract):
    """DiffPepBuilder contract with Amber-only postprocess (no Rosetta).

    Overrides ONLY ``command_preview`` step-3. Inherits everything else
    (including ``execute``, which delegates to ``runner.execute_run``) from
    the frozen ``DiffPepBuilderContract``. The frozen ``runner_contracts.py``
    is not modified.
    """

    model_id = "diffpepbuilder"

    def command_preview(self, run_id: str, input_dir: str, output_dir: str,
                        nproc: int = 1, **opts: Any) -> list[list[str]]:
        m = self.meta
        py = m["env_python"]
        src = m["source"]
        data_dir = os.path.join(output_dir, "data")
        # step 1 (preprocess) and step 2 (torchrun inference) are identical to
        # the frozen contract. Only step 3 is overridden to Amber-only.
        step1 = [
            py, os.path.join(src, "experiments", "process_receptor.py"),
            "--pdb_dir", input_dir,
            "--write_dir", data_dir,
            "--receptor_info_path", os.path.join(input_dir, "de_novo_cases.json"),
        ]
        step2 = [
            "torchrun", f"--nproc-per-node={nproc}",
            os.path.join(src, "experiments", "run_inference.py"),
            f"data.val_csv_path={data_dir}/metadata_test.csv",
        ]
        step3 = [
            py, os.path.join(src, "experiments", "amber_only_postprocess.py"),
            "--in_pdbs", os.path.join(src, "runs", "inference"),
            "--ori_pdbs", input_dir,
            "--lig_chain_id", "A",
        ]
        return [step1, step2, step3]


# Additive registry — does NOT alter the frozen ``runner_contracts._CONTRACTS``.
_AMBER_ONLY_CONTRACTS: dict[str, type[DiffPepBuilderContract]] = {
    "diffpepbuilder": DiffPepBuilderAmberOnlyContract,
}


def get_contract_amber_only(model_id: str) -> DiffPepBuilderContract:
    """Return the Amber-only contract for ``model_id``.

    Currently only ``diffpepbuilder`` has an Amber-only variant. This is an
    additive registry; the frozen ``runner_contracts.get_contract`` is
    untouched.
    """
    if model_id not in _AMBER_ONLY_CONTRACTS:
        raise KeyError(
            f"No Amber-only contract for {model_id!r}. "
            f"Available: {list(_AMBER_ONLY_CONTRACTS)}"
        )
    return _AMBER_ONLY_CONTRACTS[model_id]()


def all_amber_only_contracts() -> dict[str, DiffPepBuilderContract]:
    return {mid: cls() for mid, cls in _AMBER_ONLY_CONTRACTS.items()}
