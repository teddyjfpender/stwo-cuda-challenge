# Operating the proof-v2 challenge

The public contract is [`benchmark-proof-v2.json`](../benchmark-proof-v2.json).
Participants edit a pinned `stwo-zig` checkout through `challenge.py
setup-proof`, run exact public jobs through `benchmark-proof`, capture a
backend-specific patch, and submit a reviewable challenge PR. The
[participant task](../TASK.md), [submission instructions](SUBMISSIONS.md),
and [scoring contract](SCORING.md) are the current workflow. The retired
command-time service and its PR dispatcher are documented in
[legacy operations](LEGACY_OPERATIONS.md); its Actions ranking job is disabled.

For CPU and Metal, the designated review machine is the M5 Max. For CUDA,
use the [H200 proof-v2 runbook](H200_RUNBOOK.md). Review the exact PR head and
allowed source patch before running untrusted changes. Prepare an independent
clean baseline checkout at the same source pin, build the selected backend,
and run the same nine hash-pinned jobs into separate output directories.
Export each basket with `scripts/export_proof_v2.py --backend BACKEND`; the
exporter rehashes the emitted proofs and requires complete per-call stages.
Use `challenge.py compare-proof` for an explicitly unranked proof-time
comparison. Keep whole-command and memory diagnostics in the PR review so
proof-stage gains cannot hide a capacity failure or unusable product path.

The [site source manifest](../data/site/sources.json) points to the proof
contract and public observation TSVs. Publishing a reviewed research table
requires committing the checked TSV and manifest pointer to `main`; the
website reads that repository data through GitHub. PR claims and direct
research are never signed ranks. The [activation record](ACTIVATION.md)
tracks the remaining trusted judge, H200, independent circuit verifier,
paired baseline, and private-holdout gates. Do not enable a leaderboard until
those gates pass on the intended host for each backend.
