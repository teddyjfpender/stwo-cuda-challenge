---
name: stwo-cuda-challenge
description: Help a participant set up, optimize, validate, and package a CUDA, Metal, or CPU Cairo/recursion candidate for the staged proof-only challenge.
---

# Stwo CUDA Challenge

## Current proof-only trial

Choose one backend: `cuda` on H200, or `metal`/`cpu` on M5 Max. Read
[TASK.md](../../TASK.md) and [the proof epoch](../../spec/PROOF_STAGE_EPOCH.md).
The fixed [proof contract](../../benchmark-proof-v2.json) and
[fixture](../../fixtures/public-proof-v2.json) define the same six PIEs, two
folds, and one PIE-to-root pipeline for all three backends. Only the Cairo,
wrap, and fold prover-call intervals count; command time and memory are
diagnostics/capacity checks. Historical modeled PIE rows and current measured
rows live in the same [research TSV](../../data/reports/submission-research-2026-10-03.tsv),
with an explicit `record_kind`; modeled rows are never rank evidence.

From a fresh clone, run `git lfs pull`, `python3 challenge.py check-data`, then
`python3 challenge.py setup-proof --backend BACKEND --build`. This creates the
ignored editable checkout at `workspace/proof-v2-source` and a separate clean
`workspace/proof-v2-baseline`. Edit only that backend's `editablePaths` in the
proof contract; its protected timer files are hash-checked. For a focused
smoke, run `python3 challenge.py benchmark-proof --backend BACKEND --case-id
recursion:two-leaf-wrap-fold --out ./proof-trial --fixtures /path/to/fixtures`.
The runner checks exact reference proof/root bytes and writes an unranked
receipt with proof time separated from full-command time. The CUDA path also
requires the H200 assets and verifiers in [the runbook](../../spec/H200_RUNBOOK.md).
Test a PIE and fold before the full basket. Keep the GPU idle during repeated
baseline/candidate comparisons.

For a submission, run `python3 challenge.py capture-proof --backend BACKEND`,
commit `candidate/proof-v2-changes.patch` and a note naming the backend,
changed paths, hypothesis, before/after proof times, memory, exact proof
checks, regressions, and attribution, then open a challenge-repository PR.
Use [GitHub Discussions](https://github.com/teddyjfpender/stwo-cuda-challenge/discussions)
to compare architectures and link relevant discussions from the PR. Explore
major changes first, measure combinations, then refine the best design.
This epoch is **staging**: direct trials are reviewable research, and no
proof-only ranked judge is active yet.

## Previous H200 command-time epoch

Work from this repository's root. Read [TASK.md](../../TASK.md),
[spec/WORKLOADS.md](../../spec/WORKLOADS.md), and
[spec/SCORING.md](../../spec/SCORING.md), and
[spec/SUBMISSIONS.md](../../spec/SUBMISSIONS.md) before changing the candidate. The
versioned contract in [benchmark.json](../../benchmark.json) fixes the source
commit, editable paths, workloads, and security profile.

Use `python3 challenge.py --help` for the participant CLI. Run `python3 challenge.py setup` to create the ignored pinned editable checkout at `./workspace/stwo-zig/` (singular `workspace`), then `python3 challenge.py paths` to print its absolute location. [spec/CODE_MAP.md](../../spec/CODE_MAP.md) gives exact CUDA files and purposes; edit only the five `benchmark.json` directories. Use `capture` to produce `candidate/changes.patch`; keep
`candidate/NOTES.md` current with the hypothesis, focused checks, and measured
results. The judge rebuilds from that patch, so a local binary is never the
ranked submission.
The editable checkout begins with the reviewed
[accepted frontier](../../frontier/manifest.json); the baseline stays at the
original pin. Capture produces a cumulative patch containing the frontier and
your changes. Use `setup --base` only in a fresh checkout when inspecting the
original source.
The current cumulative frontier is challenge PR #17, including challenge PR #6
and upstream `stwo-zig` PR #205.
After pulling challenge `main`, rerun `setup` to advance an unchanged old
frontier. Capture source edits first and transfer them to a fresh checkout;
setup refuses to overwrite participant changes. PR #17's direct H200
measurements are unranked research, not judge scores.

Use [GitHub Discussions](https://github.com/teddyjfpender/stwo-cuda-challenge/discussions)
to compare design alternatives and profiler evidence. An Ideas thread should
name a measurable bottleneck, mechanism, prediction, and smallest falsifying
case; Show and tell is for verified public measurements. Link useful threads
from the eventual PR. Never post private fixtures, keys, or proof blobs.

Search in three passes: explore architecture-level changes across the whole
PIE/recursion/pipeline path, compose independent measured wins, then exploit
the best combination with smaller improvements. For each hypothesis, write
down the target phase, expected minimum full-command gain, memory effect, and
one cheap case that could reject it. Compare alternatives before spending H200
time on minor kernel tuning. Record failed compositions and regressions.

Prefer a focused local check before a public H200 smoke case. On a prepared
H200 host, use `setup --build`, then `benchmark --tier smoke`, followed by
`benchmark --tier qualify` for the full basket. Use `--tier rank` only after
qualification. Every case must produce its canonical, independently verified
proof at the fixed security settings. Consult [README.md](../../README.md) for
host prerequisites and [spec/H200_RUNBOOK.md](../../spec/H200_RUNBOOK.md) for
operator-only H200 setup.
The [fixed-artifact release](../../spec/RELEASE_ARTIFACTS.md) can supply
hash-verified Rust verifiers and canonical preprocessing data on a supported
Linux host; setup falls back to pinned source builds if no release is pinned.
On a mounted persistent volume, the operator should first run
`python3 scripts/h200_preflight.py --mode prepare` on a CPU host to verify
those assets and public fixtures before renting GPU time. `--mode direct`
then checks the live H200, and `--mode judge --image SHA256_ID` also checks
the sandbox image before any ranked proof. Keep one GPU experiment at a time.
An operator should run
`python3 scripts/h200_preflight.py --mode direct` before direct diagnostics;
`scripts/h200_experiment.py` then records a paired PIE and fold/pipeline
smoke with source/binary identity and opens the full basket only if the stated
stage, target command, and companion guard pass. For a verified CUDA/NVTX
timeline and whole-device memory trace, follow
[spec/H200_PROFILING.md](../../spec/H200_PROFILING.md); its instrumented time is
diagnostic. A restricted research pod cannot stand in for a sandboxed
ranked judge.

Keep proof-stage telemetry separate from ranked adapted-input-to-publication
wall time. The measured phases are in [data/reports](../../data/reports/README.md).
The current [activation record](../../spec/ACTIVATION.md) describes what must
be enabled before a live ranked submission can run. Do not present local or
direct H200 results as leaderboard scores.

Complete `candidate/NOTES.md`, commit and push it with
`candidate/changes.patch` to a challenge fork, and open a PR against the
challenge repository for review. Explain changed paths, mechanism, before and
after public time and peak memory, checks, regressions, tradeoffs, any model or
harness used, and related Discussions. For this internal challenge, the PR is
the manual queue entry: the operator reviews it, freezes its exact head SHA
with `service/pr_batch.py`, and later starts the trusted builder and judge.
The optional HTTP intake is not needed for a PR submission. Opening a PR does
not start paid GPU work or create a ranked score; only a signed judge receipt
does. [spec/SUBMISSIONS.md](../../spec/SUBMISSIONS.md) defines the current
sequence.
