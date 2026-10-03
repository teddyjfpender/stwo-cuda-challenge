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

## Previous H200 command-time epoch

The goal is to make the pinned H200 CUDA prover faster or use less device
memory **across the full Cairo PIE, recursive-fold, and PIE-to-root basket**.
Every required proof must still verify with the pinned independent verifier,
match its expected public output, use the canonical security profile, and have
no CPU proving fallback. The actual `h200-v1` score measures adapted-input to
published-proof wall time and whole-device peak memory. Read
[`WORKLOADS.md`](WORKLOADS.md) and [`SCORING.md`](SCORING.md) before optimizing.

## Research and design

Use [GitHub Discussions](https://github.com/teddyjfpender/stwo-cuda-challenge/discussions)
to compare architectures, profiler findings, memory plans, and failed as well
as successful experiments. Start an **Ideas** thread for a falsifiable design
hypothesis, **Q&A** for setup or verification help, and **Show and tell** for
reproducible public measurements. Link relevant threads from the eventual PR;
discussion is encouraged, not a prerequisite to run local tests. Keep private
holdouts, credentials, proof blobs, and unpublished inputs out of Discussions
and PRs. [`DISCUSSIONS.md`](DISCUSSIONS.md) describes the forms and evidence.

Work through exploration, composition, then exploitation. Profile the
complete PIE/recursion/pipeline path and propose several architecture-level
changes with explicit expected phase, command-time and memory effects. Use
focused checks to reject weak ideas early. Combine independently promising
changes, remeasure interactions, and only then spend H200 time on small local
refinements. Submission notes should include the prediction, the smallest
falsifying test, combinations attempted, before/after full commands and
whole-device peaks, regressions, and exact proof checks.

## Edit and validate

1. Fork this challenge repository. Run `git lfs pull`,
   `python3 challenge.py check-data`, and `python3 challenge.py setup` from its
   root. Setup creates the pinned `./workspace/stwo-zig/` checkout (singular `workspace`; ignored in Git). Run `python3 challenge.py paths` to print its absolute location. [CODE_MAP.md](CODE_MAP.md) names specific CUDA entry points.
   The editable checkout starts with the reviewed
   [accepted frontier](../frontier/manifest.json) applied over the immutable
   source pin. `workspace/baseline` remains clean. `setup --base` leaves a
   fresh checkout at the original pin for comparison. The current cumulative
   frontier is challenge PR #17, including challenge PR #6 and upstream
   `stwo-zig` PR #205. Pull
   challenge `main` and rerun `setup` to advance an unchanged older frontier.
   If you have source edits, capture them first and apply them to a fresh
   checkout; setup will not overwrite participant work.
2. Edit production prover code **only** under these `benchmark.json`
   `editablePaths` in `workspace/stwo-zig`:

   | Path | Typical work |
   | --- | --- |
   | `src/backends/cuda/` | Device runtime, allocation, kernels, scheduling, transfers. |
   | `src/integrations/cairo_cuda/` | Cairo witness, AIR, proof execution, ingress and publication. |
   | `src/integrations/circuit_cuda/` | CUDA circuit execution, wrap and fold integration. |
   | `src/products/cairo_cuda/` | Cairo CUDA product wiring and reporting. |
   | `src/products/circuit_recursion_cuda/` | Recursive CUDA product wiring and reporting. |

   CPU, Metal, and Rust code may inform a design but are outside the candidate
   edit surface. Do not change the challenge's fixture manifest, security,
   verifier, scoring, timers, or judge. The capture command refreshes derived
   CUDA manifests; do not hand-edit them.
3. Write a hypothesis with a target phase, predicted full-command gain and
   memory effect. Use the smallest relevant compile or focused test. The
   operator can run `scripts/h200_preflight.py --mode prepare` on a CPU host
   with the persistent volume to verify fixtures and release assets before
   renting GPU time. Before proving, run `--mode direct` (and `--mode judge`
   with the pinned sandbox image for a ranked host). On a prepared H200, run
   `python3 challenge.py setup --build` and
   `python3 challenge.py benchmark --tier smoke --track balanced`. Run
   one independently verified PIE and a fold/pipeline case, then repeated
   baseline/candidate measurements on an otherwise idle H200. Record source
   and binary IDs, proof hashes, stage times, external command time, and
   whole-device peak. `scripts/h200_experiment.py` gates the full basket on
   the target command and companion case. Run `--tier qualify` for the
   complete basket only when those focused checks show a credible gain;
   use `--tier rank` for paired measurements. Record the exact case, hardware,
   samples, end-to-end time, peak device bytes, proof checks, and regressions.
   Local measurements are research evidence, not leaderboard scores.
4. Run `python3 challenge.py capture` after editing. It automatically includes
   new files under the allowed CUDA paths and writes
   `candidate/changes.patch` from the cumulative allowed source diff and checks
   that it applies to the original pinned commit. Keep the inherited frontier
   changes in that patch. Fill in `candidate/NOTES.md`.

## Reviewable PR and judged submission

Push `candidate/changes.patch` and `candidate/NOTES.md` to your **fork of this
challenge repository** and open a PR against its `main` branch. The PR is the
human-review surface: describe the bottleneck, design, changed CUDA paths,
public measurements and proof checks, tradeoffs, model/harness attribution,
and related Discussions. GitHub's PR template prompts for these items. The
patch contains the production source changes; `workspace/`, generated proofs,
logs, and binaries are not PR artifacts. A submission PR need not be merged
into the challenge's `main` branch to be judged. An operator-accepted cumulative
patch is copied to `frontier/changes.patch` with exact PR and patch identities
in `frontier/manifest.json`; new participants receive it automatically. This
does not change the original baseline or create a ranked score. Upstream
`stwo-zig` adoption is a separate source review.

For this internal challenge, **the PR is enough to enter the operator's daily
queue**. An operator reviews it and applies the `ready-to-judge` label. The
batch collector freezes that PR's full head SHA, reads the patch and notes
from that commit, validates them through immutable intake, and records the PR
number, SHA, and submission ID together. Pushing another commit creates a new
candidate; the old judged result still belongs to its original SHA. A PR does
not trigger paid GPU work automatically. The operator starts the H200 batch
and publishes independently verified signed receipts afterward. No public
intake endpoint or participant API key is needed for this workflow.

A complete candidate submission includes:

- A nonempty `candidate/changes.patch` affecting only allowed CUDA paths and
  applying to the pinned source commit.
- `candidate/NOTES.md` with a mechanism, affected paths, focused and public
  validation, measured time and memory, correctness evidence, tradeoffs,
  model/harness attribution, and relevant Discussion links.
- An immutable fork commit; for human review, a PR linking that commit and
  explaining the claimed improvement. A claim remains unranked until the
  operator publishes an independently verified, signed rank receipt.

The standalone HTTP intake remains available for a future self-service mode,
but its shared bearer token is not a participant credential. The manual PR
batch and its setup are in [`OPERATIONS.md`](OPERATIONS.md).
