# CUDA proof-v2 trial on an H200

The current challenge measures only Cairo, wrap, and fold prover-call
intervals for the nine jobs in [`benchmark-proof-v2.json`](../benchmark-proof-v2.json).
The same inputs and expected proof/root hashes are used for CPU and Metal.
The H200 direct runner is an **unranked research tool**; no proof-v2 judge or
signed ranking receipt is active yet. The former command-time operator
procedure is [archived](LEGACY_H200_RUNBOOK.md).

Use an idle H200 with enough persistent storage for the Git LFS inputs,
fixed preprocessing data, source, build cache, and proof outputs. Keep
results and cache outside the Git worktree. The CUDA build helper targets
SM 90 and uses nvcc threads and ccache when available; set
`STWO_CUDA_BUILD_CACHE_ROOT` to persistent storage before building.

```sh
git lfs pull
python3 challenge.py check-data
python3 harness/check_contract.py
python3 challenge.py setup-proof --backend cuda --build --build-baseline
python3 challenge.py paths --backend cuda
```

`setup-proof --build --build-baseline` pins `stwo-zig@1433d61b`, builds the CUDA Cairo and
resident circuit products, and prepares the canonical fixed asset, staged
AIR bundles, and two independently built Rust Cairo verifiers. The current
fixed-asset release is pinned to the older epoch, so this source pin falls
back to building those tools; keep the resulting `.cache` and Zig/Cargo
caches on persistent storage. A future release for the proof-v2 source pin
can eliminate that repeated preparation. No candidate binary is accepted
as a verifier.

Before measuring, run the machine-checked proof-v2 preflight. `prepare`
rehashes fixed assets and selected fixtures; `direct` additionally requires
an idle H200 and no concurrent build process. Both are prerequisite checks,
not score receipts. There is deliberately no proof-v2 `judge` mode yet.

```sh
python3 scripts/h200_preflight.py --mode prepare \
  --config benchmark-proof-v2.json --manifest fixtures/public-proof-v2.json \
  --source workspace/proof-v2-baseline --out /external/trials/prepare.json
python3 scripts/h200_preflight.py --mode direct \
  --config benchmark-proof-v2.json --manifest fixtures/public-proof-v2.json \
  --source workspace/proof-v2-baseline --out /external/trials/direct.json
```

Run one PIE and one recursive case first. `--out` directories must be fresh;
the full basket checks all nine exact output hashes and reports both proof
time and whole-command time. Use `--fixtures` if the hash-pinned input store
is mounted elsewhere.

```sh
python3 challenge.py benchmark-proof --backend cuda \
  --case-id pie:15582797_15582797 --out /external/trials/pie
python3 challenge.py benchmark-proof --backend cuda \
  --case-id recursion:two-leaf-wrap-fold --out /external/trials/fold
python3 challenge.py benchmark-proof --backend cuda \
  --out /external/trials/baseline --source workspace/proof-v2-baseline
python3 scripts/export_proof_v2.py --backend cuda \
  --root /external/trials/baseline --out /external/trials/baseline.tsv
```

After an allowed CUDA source edit, rebuild the editable checkout, run the same
basket into a separate directory, export it, then compare proof times:

```sh
python3 challenge.py setup-proof --backend cuda --build --skip-assets
python3 challenge.py benchmark-proof --backend cuda \
  --out /external/trials/candidate --source workspace/proof-v2-source
python3 scripts/export_proof_v2.py --backend cuda \
  --root /external/trials/candidate --out /external/trials/candidate.tsv
python3 challenge.py compare-proof --backend cuda \
  --baseline /external/trials/baseline.tsv \
  --candidate /external/trials/candidate.tsv \
  --out /external/trials/comparison.json
python3 challenge.py capture-proof --backend cuda
```

The exporter checks the source pin and protected timer digest, requires the
right number of Cairo, wrap, and fold intervals, and rehashes the emitted
proof or root. The direct JSON also retains whole-device peak, arena plan,
Rust Cairo verifier results, proof hashes, command time, and binary identity.
An idle host, multiple paired repetitions, and a trusted measurement boundary
are required before promoting an improvement. Do not run the retired
`h200-rank.yml` workflow; it is disabled and scores the wrong epoch.
