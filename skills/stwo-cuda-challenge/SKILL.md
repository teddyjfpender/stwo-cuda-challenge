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
