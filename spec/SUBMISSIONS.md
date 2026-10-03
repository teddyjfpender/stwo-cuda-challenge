# Participant workflow and submissions

## Proof-only CUDA, Metal, and CPU trial

The current staged trial uses [`benchmark-proof-v2.json`](../benchmark-proof-v2.json)
and the same nine jobs in [`public-proof-v2.json`](../fixtures/public-proof-v2.json)
for each backend. Pick one of `cuda`, `metal`, or `cpu`. Run
`python3 challenge.py setup-proof --backend BACKEND --build`; edit the selected
backend's allowed directories under `workspace/proof-v2-source`; use
`python3 challenge.py benchmark-proof --backend BACKEND --case-id
recursion:two-leaf-wrap-fold --out ./proof-trial --fixtures /path/to/fixtures`
for an exact-output smoke check. `--case-id` can be omitted for the full public
basket. The CUDA trial requires the H200 setup in [H200_RUNBOOK.md](H200_RUNBOOK.md).

Only prover-call time for Cairo, wrap, and fold proofs is the proposed score.
Whole-command time, input preparation, publication, verification, and memory
must be reported separately; memory is a capacity gate. Every submitted job
must reproduce the hash-pinned proof/root at canonical security. Timing files
are protected and checked before a run. Direct trials are **unranked** until
the paired, sandboxed proof-only judge and fresh per-backend baselines qualify.

Run `python3 challenge.py capture-proof --backend BACKEND` and submit
`candidate/proof-v2-changes.patch` plus a short notes file in a reviewable PR.
Name the backend, changed source paths, bottleneck and mechanism, expected and
observed proof-stage gain, command and memory diagnostics, exact verification,
regressions, and model/harness attribution. Link useful
[Discussions](https://github.com/teddyjfpender/stwo-cuda-challenge/discussions).
The old CUDA command-time submission format below belongs to `h200-v1` and
cannot create a proof-only rank.
