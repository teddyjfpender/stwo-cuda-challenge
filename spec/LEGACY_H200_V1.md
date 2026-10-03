# Archived H200 command-time challenge

The material below documents the retired `h200-v1` workflow. It is retained for interpreting historical receipts and is not the current participant task or scoring contract.

## Former README

# Stwo CUDA Challenge

The [proof-only multi-backend trial](spec/PROOF_STAGE_EPOCH.md) is now available
for local testing. It uses the same nine unique canonical jobs on CUDA H200,
Metal M5 Max, and CPU M5 Max; only Cairo, wrap, and fold prover intervals
enter its staged score. Start at the [agent task](TASK.md#proof-only-cuda-metal-and-cpu-trial)
and use `challenge.py setup-proof`, `benchmark-proof`, and `capture-proof`.
Exact output checks and protected timer hashes are implemented, but the
paired sandboxed judge and fresh backend baselines are still qualification
gates. Trial results are unranked until those gates pass.

Optimize the production Cairo and circuit-recursion CUDA paths in
[`stwo-zig`](https://github.com/teddyjfpender/stwo-zig) on one H200. The ranked
workload starts with **already adapted** Starknet PIE inputs, proves each PIE,
wraps Cairo proofs in circuit verifier proofs, and folds consecutive leaves to
one recursive root. The judge owns the inputs, clock, memory measurement,
security settings, independent Cairo verification, and canonical root checks.

**Launch scope:** the intended research target is GPU proving time. The
implemented `h200-v1` judge currently scores the full adapted-input-to-proof
command, including ingress and publication, and is **not live**. Six Cairo PIE
proof-stage timings are retained (1.17–1.95 s); wrap/fold proof-only timers are
still missing. The [activation decision](spec/ACTIVATION.md) requires a new
proof-stage scoring epoch and fresh baselines before a proving-time leaderboard
can open. The direct 6.90–9.78 s Cairo figures are full-command diagnostics.
The [staging website](https://autoresearch-web-lac.vercel.app/challenges/stwo-cuda)
accepts no ranked submissions; it links to this repository for research PRs
and Discussions.
The reviewed [PR status](data/site/sources.json) and per-case research
measurements selected by that manifest are published separately from signed
scores. The [accepted starting frontier](frontier/manifest.json) is a cumulative
patch: challenge PR #17 builds on challenge PR #6 and the ingress changes
merged upstream in `stwo-zig` PR #205. PR #17 has direct H200 research
measurements, but no judged ranking. Pull challenge `main` and rerun setup to
pick up that reviewed source.
PR #4's narrower [PoW primitive results](data/reports/submission-pow-primitives-2026-10-02.tsv)
are retained alongside its full-command regressions.
The [upstream PR #212 H200 ingress study](data/reports/README.md#upstream-cuda-ingress-pr-212-2026-10-03)
records two- and four-distinct-PIE ABBA timings and exact proof hashes as
unranked research; it does not change this challenge's fixed source pin or
accepted participant frontier.

The prover's CUDA implementation lives in upstream `stwo-zig`. This challenge
pins one commit from its `main` branch and checks it out under
`workspace/stwo-zig` after `python3 challenge.py setup`. Setup overlays the
reviewed cumulative CUDA [frontier patch](frontier/changes.patch) by default; `--base`
leaves a fresh checkout at the original pin. Participants submit cumulative
changes to the allowed CUDA paths as
`candidate/changes.patch` in their challenge-repository PRs. The judge applies
that full patch to a clean pinned checkout before building and measuring it. This
keeps one production source tree and gives maintainers a source diff to apply
or rebase upstream. A PR should explain its CUDA changes in
`candidate/NOTES.md`; the patch is the reviewable source diff, not a binary
artifact. The challenge's `harness/` contains only measurement and validation
code. `./setup.sh` obtains the exact source commit and accepted frontier. Public inputs and retained
reference proofs are under
[`data/`](data/README.md), with the scored fixture contract in
[`fixtures/public-v1.json`](fixtures/public-v1.json).

Start with [TASK.md](TASK.md) and the [exact CUDA source map](spec/CODE_MAP.md).
Run `python3 challenge.py paths` to see the local checkout path; there is no
`/workspaces/stwo-zig` directory, and `workspace/` is ignored in Git. A fresh
clone therefore has no prover source until setup runs. The fixed contract is [benchmark.json](benchmark.json),
the workload and proof obligations are in [spec/WORKLOADS.md](spec/WORKLOADS.md),
and the scoring and tradeoffs are in [spec/LEGACY_SCORING.md](spec/LEGACY_SCORING.md).
The [submission guide](spec/SUBMISSIONS.md) lists editable CUDA files,
validation, Discussion use, PR contents, and the separate judge intake step.
Coding agents can load the repository's
[participant skill](skills/stwo-cuda-challenge/SKILL.md); its commands are
available through [`challenge.py`](challenge.py). Both use paths relative to
this checkout.
The specific upstream design choices are recorded in
[spec/REFERENCES.md](spec/REFERENCES.md). The exact boundary before enabling
the live H200 leaderboard is in [spec/ACTIVATION.md](spec/ACTIVATION.md).

Three rankings use the **same validated proofs and measurements**. The public
basket currently has six component-diverse PIEs, two fixed-leaf root folds
(two leaves and eight distinct contiguous leaves), and two full PIE-to-root
modes (serial and integrated batch):

| Track | Objective | Why it exists |
| --- | --- | --- |
| `latency` | Minimize the weighted geometric mean of adapted-input-to-publication time | Fastest usable H200 pipeline. |
| `memory` | Minimize the weighted geometric mean of whole-device peak bytes, with a latency guard | Make dense PIEs fit and enable later GPU choices. |
| `balanced` | Minimize normalized time × peak memory, with per-case guardrails | Explore the Pareto tradeoff; a capacity proxy, not a dollar-cost claim. |

Every score card publishes the uncompressed per-case `(time, memory)` ratios;
`harness/frontier.py` derives Pareto status across judged submissions.
Correctness is a hard gate for **all** tracks. The
ranked suite is fixed by a versioned, hash-pinned manifest; holdout inputs use
the same public shape classes. There is no score from a self-reported kernel
timer, a source-only static estimate, or an unverified proof.

## Development loop

1. Prepare Zig 0.15.2, CUDA/nvcc, ccache 4.0+, Cargo,
   `nightly-2026-01-15`, and
   `git lfs pull` on a Linux H200 workspace. Keep the toolchain, fixtures,
   checked preprocessing asset, verifiers, and baseline build on a reusable
   volume. Set `STWO_CUDA_BUILD_CACHE_ROOT` to a persistent directory;
   setup shares its archive/cubin and ccache entries between baseline and
   candidate builds while targeting only SM 90. The reviewed
   [fixed-artifact release](spec/RELEASE_ARTIFACTS.md) lets setup
   download hash-verified Rust verifiers and canonical preprocessing data
   instead of rebuilding those unchanged inputs. The operator runs
   `scripts/h200_preflight.py --mode direct` before
   research proofs. A separate ranked judge host also needs Docker/NVIDIA,
   mount privileges, and the pinned sandbox image; its
   `--mode judge --image SHA256_ID` preflight fails before proof work if those
   gates are missing. `./setup.sh` creates the pinned baseline and editable
   checkout; it does not download private PIEs.
2. Run `python3 challenge.py paths`, then work in `workspace/stwo-zig` under
   the [allowed CUDA source paths](spec/CODE_MAP.md). The checkout already
   contains the accepted frontier; the baseline remains the original pin.
   After pulling challenge `main`, rerun `python3 challenge.py setup` to pick
   up a newer frontier. An unchanged previous frontier advances automatically;
   if you have source edits, capture them first and move them onto a fresh
   checkout. Setup will not overwrite participant changes.
   Explore architecture
   hypotheses first, test whether independent wins compose, then refine the
   surviving design. Name the expected stage and minimum gain; run relevant
   small local tests before a GPU trial.
3. Capture the source diff with `./scripts/capture-candidate.sh`. Optionally
   attach a prebuilt binary digest for the fast screening tier. The binary is
   never a substitute for source in a ranked submission.
   Capture refreshes the derived CUDA manifests after kernel edits. The trusted
   builder checks them against source and pinned product policy; only the
   unmodified baseline must match the immutable upstream import hash.
4. Build both arms, the pinned Rust verifiers, and the canonical preprocessing
   asset with `./setup.sh --build`. On an idle H200, run a verified PIE and
   fold/pipeline A/B smoke with `scripts/h200_experiment.py`; its stage-gain
   gate prevents weak hypotheses from launching the full basket. The direct
   driver journals source/binary hashes, cold command, phase times, proof
   hashes, and whole-device peak for every run. A trusted `rank` run separately
   performs three ABBA rounds and emits signed scores only on a qualified
   sandboxed judge; direct results remain research evidence.
   For a verified one-case GPU timeline and 10 ms whole-device memory trace,
   use the [profiling runbook](spec/H200_PROFILING.md) before choosing a kernel
   or buffer-lifetime experiment. Profiled wall time is diagnostic.

On a prepared H200 host, the local loop is:

```sh
git lfs pull
python3 challenge.py check-data
python3 challenge.py setup
python3 challenge.py paths
# Edit allowed CUDA source paths in workspace/stwo-zig.
python3 challenge.py capture
python3 challenge.py setup --build
python3 challenge.py benchmark --tier smoke --track balanced
```

Use `python3 challenge.py benchmark --tier qualify` for all cases once and
`--tier rank` only on a qualified judge. The original `setup.sh`,
`scripts/capture-candidate.sh`, and `benchmark.sh` remain equivalent direct
entry points; `python3 challenge.py --help` lists the participant commands.
To package a candidate, update `candidate/NOTES.md`, then commit and push
`candidate/changes.patch` and `candidate/NOTES.md` in your challenge fork.
Open a PR against this challenge repository for review and link any relevant
[research Discussions](spec/DISCUSSIONS.md). Opening a PR does not start a
GPU run or constitute a ranked submission.
For this internal challenge, the PR enters a manual daily review queue.
The operator freezes its number and exact head SHA with `service/pr_batch.py`;
the optional HTTP intake is not required. The checked-in
[activation record](spec/ACTIVATION.md) tracks the later ranked-judge gate.
The benchmark defaults to the checked-in public inputs and setup assets under
`.cache/`; operator paths and the private manifest can be supplied with CLI
flags or the `STWO_*` variables shown in `.github/workflows/h200-rank.yml`.
The checked-in public files use Git LFS: run `git lfs pull` and
`python3 scripts/check_data.py` after cloning. In deployment the judge may
mount its own read-only content-addressed store with the same manifest-relative
paths. Run `python3 scripts/materialize_public.py --source workspace/stwo-zig
--out data/inputs --verify-only` to check the original public fixture contract
before spending GPU time. The canonical preprocessing
asset is generated from the pinned prover with `zig build
cairo-preprocessed-export -Doptimize=ReleaseFast` followed by
`zig-out/bin/cairo-preprocessed-export /absolute/path/preprocessed-canonical.bin
canonical`. Keep the 2 GiB asset outside Git.

Standalone PIE proofs use the pinned `stwo-cairo-official-verifier`. Registry
leaf proofs use the pinned Rust `verify_cairo_cuda_json` helper because their
Blake2s-M31/lifted proof shape is different. `./setup.sh --build` creates both
verifiers from the pinned baseline source; `--registry-cairo-verifier` can
override the latter path when using operator-managed assets.

Participants do not need the PIE API key. The operator creates a static
content-addressed bundle once, then hosts that directory over HTTPS:

```sh
python3 scripts/publish_public.py \
  --source data/inputs \
  --out ../stwo-cuda-challenge-public-bundle
python3 scripts/fetch_public.py \
  --base https://your-fixture-host.example/challenge/h200-v1 \
  --out data/inputs
```

The downloader checks the committed manifest digest and every blob SHA-256.
`--case-id` fetches only one case for a cheap smoke loop. The public bundle is
prepared locally; its HTTPS hosting remains part of deployment.

The service/runner design, artifact policy, isolation requirements, and H200
budget controls are in [spec/JUDGE.md](spec/JUDGE.md). The
[H200 operator runbook](spec/LEGACY_H200_RUNBOOK.md) gives the activation sequence.
The [operations map](spec/LEGACY_OPERATIONS.md) explains how PRs, intake, GitHub
Actions, signed receipts, and `autoresearch-web` fit together and which live
connections still need deployment.
For the internal daily batch, an operator reviews PRs, adds the
`ready-to-judge` label, and freezes their exact heads into local intake state:

```sh
python3 service/pr_batch.py --dry-run
python3 service/pr_batch.py --source workspace/baseline \
  --state /operator/state
```

The standalone HTTP intake prototype and trusted dispatcher also remain
runnable locally:

```sh
python3 service/intake.py --source workspace/baseline \
  --state ../stwo-cuda-challenge-state --token-file /secure/path/intake-token \
  --max-intake-requests-24h 100
python3 service/build_worker.py --source workspace/baseline \
  --state ../stwo-cuda-challenge-state --submission-id ID
python3 service/dispatch.py --source workspace/baseline \
  --state ../stwo-cuda-challenge-state --submission-id ID \
  --repository teddyjfpender/stwo-cuda-challenge --tier smoke --dry-run
```

`POST /submissions` takes `{"repository":"https://github.com/OWNER/FORK",
"commit":"FULL_SHA"}` and an optional `artifact_sha256`. It returns a job ID
after patch validation, without building or reserving the H200. The worker
rebuilds ranked binaries from source; uploaded artifacts are stored for future
untrusted fast screening only. A real H200 deployment requires a fixture
object store, verifier binaries, self-hosted runner, isolation, an externally
provisioned receipt signing key, chosen GPU dispatch budgets, and operator
secrets outside Git. Intake's request limit is persistent across restarts.
This repo does not claim to operate a live public ranking service yet.

The [public staging repository](https://github.com/teddyjfpender/stwo-cuda-challenge)
has Discussions enabled. Once an operator configures the dedicated H200
runner and judge variables, removing `--dry-run` dispatches a built submission
to the serialized workflow. Smoke, qualify, and rank receipts remain available
by tier as a submission progresses.
The manual `CPU sandbox probe` workflow exercises the image and filesystem
boundary on a hosted Linux runner; H200 GPU proof parity remains a separate
activation gate.

The current GitHub Discussions categories and research forms are in
[spec/DISCUSSIONS.md](spec/DISCUSSIONS.md). No benchmark source, proof blob,
API token, or private fixture belongs in a Discussion or submission PR.

## Former task


Improve CUDA proving of Starknet Cairo PIEs and their recursive aggregation on
one H200. The fixed basket covers standalone PIE proofs, two- and eight-leaf
folds, and two complete PIE → Cairo proof → wrap → fold → root modes. Optimize
adapted-input-to-published-proof time and whole-device peak memory while
preserving every proof, security, and source-policy requirement. All cases and
track guards matter; read [`WORKLOADS.md`](spec/WORKLOADS.md),
[`LEGACY_SCORING.md`](spec/LEGACY_SCORING.md), and
[`SUBMISSIONS.md`](spec/SUBMISSIONS.md) before editing.

Run `python3 challenge.py setup` from the challenge root to create the ignored,
editable prover checkout at **`./workspace/stwo-zig/`** (singular `workspace`).
It is absent from GitHub and fresh clones. Run `python3 challenge.py paths` to
print the absolute local paths. [CODE_MAP.md](spec/CODE_MAP.md) names the exact
files to inspect and edit. The checkout begins with the reviewed
[accepted frontier](frontier/manifest.json)
over the immutable pinned prover source. `challenge.py capture` emits a
**cumulative** patch against the original pin, including the frontier and your
new work; do not strip the inherited changes. To inspect the original baseline
in a fresh checkout, use `challenge.py setup --base`.
The current cumulative frontier is challenge PR #17, including challenge PR #6
and upstream `stwo-zig` PR #205.
After updating challenge `main`, rerun `setup`: an unchanged old frontier
advances automatically. If you have edits, capture your patch first and apply
your changes to a fresh checkout; setup refuses to discard them. PR #17's
direct H200 measurements are unranked research, separate from judge scores.
The five allowed CUDA directories and their purposes are listed in
`spec/SUBMISSIONS.md` and
`benchmark.json`. Use CPU, Metal, and Rust implementations for understanding,
but change production code only in those CUDA directories. The challenge
contract, judge, verifier, fixture manifest, security profile, and reference
outputs are outside the candidate edit surface. `challenge.py capture`
refreshes derived CUDA manifests and writes the restricted
`candidate/changes.patch`; do not hand-edit those manifests or the patch.

Investigate substantial bottlenecks in witness/lookup storage, host/device
transfer, kernel layout, fixed-asset reuse, scheduling, wrap/fold construction,
and publication. Form a falsifiable hypothesis, measure phases and memory,
then test the smallest public case that could disprove it. Use
[GitHub Discussions](https://github.com/teddyjfpender/stwo-cuda-challenge/discussions)
to debate architectures, compare evidence, and share unsuccessful ideas. Link
useful threads from the PR. Discussions are a research channel, not an
alternative to proof checks or a ranked receipt.

Explore several architectural changes before settling on local tweaks. For
each, predict which measured ingress, proof, recursion, or publication phase
should improve, by how much, and at what memory cost. Combine independent
strong changes and measure whether they compose; then refine the surviving
design greedily. A fast PoW or hash primitive that leaves the ten-case command
and memory results unchanged is research evidence, not a winning submission.

Keep the development loop small: focused compile/test, a verified public PIE
and fold/pipeline smoke, repeated idle-host A/B, then complete qualification
when promising. The operator's direct
[`h200_experiment.py`](scripts/h200_experiment.py) records exact identities,
phase times, proof hashes, and peaks; its results are unranked. Standalone Cairo proofs
need the pinned official Rust verifier; pipeline leaves need the pinned
production-registry Rust verifier; every recursive root must bind the correct
contiguous leaves and outputs. Record all regressions and the exact timing
scope. A faster kernel alone is not an end-to-end improvement.

Finish by completing `candidate/NOTES.md`, capturing the patch, and opening a
reviewable PR in this challenge repository. That PR is separate from the
operator's immutable-commit intake and H200 dispatch. The PR must explain the
changed paths, mechanism, before/after public measurements and memory,
correctness checks, tradeoffs, attribution, and related Discussions.

## Former participant skill


Work from this repository's root. Read [TASK.md](../../TASK.md),
[spec/WORKLOADS.md](../../spec/WORKLOADS.md), and
[spec/LEGACY_SCORING.md](../../spec/LEGACY_SCORING.md), and
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
host prerequisites and [spec/LEGACY_H200_RUNBOOK.md](../../spec/LEGACY_H200_RUNBOOK.md) for
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

## Former submission guide


The goal is to make the pinned H200 CUDA prover faster or use less device
memory **across the full Cairo PIE, recursive-fold, and PIE-to-root basket**.
Every required proof must still verify with the pinned independent verifier,
match its expected public output, use the canonical security profile, and have
no CPU proving fallback. The actual `h200-v1` score measures adapted-input to
published-proof wall time and whole-device peak memory. Read
[`WORKLOADS.md`](WORKLOADS.md) and [`LEGACY_SCORING.md`](LEGACY_SCORING.md) before optimizing.

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
batch and its setup are in [`LEGACY_OPERATIONS.md`](LEGACY_OPERATIONS.md).

## Former activation record

# H200 activation record

**Launch decision: staging, not open for ranked submissions (2026-10-02).**
The implemented `h200-v1` contract scores full-command time, while the intended
research target is GPU proving time. The website now foregrounds the six
retained Cairo proof-stage measurements and labels full-command measurements
separately. The next proof-stage epoch now has a defined judge-owned boundary
in [`PROOF_STAGE_EPOCH.md`](PROOF_STAGE_EPOCH.md), but its trusted adapter,
timers, and fresh paired baselines are not implemented. Do not launch the
full-command v1 ranking as though it were the proving-time challenge. Agents can use
the generated checkout, publish research in Discussions, and open review PRs
now. No PR or website number is a ranked result until the gates below are
qualified and the judge publishes a signed rank receipt. The operator should
keep the site's status at `staging` and should not advertise a live intake URL
or leaderboard while the runner, isolation, paired baseline, and receipt feed
are absent. The [source map](CODE_MAP.md) specifies exactly what agents edit.

This is the boundary between a tested challenge repository and a live ranked
service. The repository is public. No self-hosted H200 runner or
GitHub Actions judge variables are configured, so the manual H200 workflow
must not be dispatched yet. The concrete setup sequence is in
[`LEGACY_H200_RUNBOOK.md`](LEGACY_H200_RUNBOOK.md).

As checked on 2026-10-02, GitHub lists zero self-hosted runners for this
repository, and `service/activation.py` reports all ten H200 judge variables
missing. The funded Runpod session qualified the public proofs directly but
did not change these live-service gates. A 2026-10-02 inspection of the
available H200 pod found neither Docker nor `CAP_SYS_ADMIN`; it cannot mount
the judge's per-case output images or qualify the isolated rank workflow.
That research pod was stopped; it was never registered as a judge.
The later independent PR #6 comparison added three direct ABBA rounds across
all ten public cases, with exact canonical proofs and Rust verification. It
improved every PIE's full command but did not supply isolation, private
holdouts, or a signed rank receipt; its three-family direct gain was also
below that session's A/A noise threshold. PR #6 is promoted in the public
research record, not the ranked leaderboard. The paid H200 pod was stopped
after these measurements.
On 2026-10-03, challenge PR #17 passed an independent direct H200 comparison
against the frozen pin with three full-basket passes per arm and exact public
proof/root checks. It was accepted as the unranked cumulative source frontier;
its [measurements](../data/reports/README.md) and locally copied service
artifacts do not satisfy sandbox, private-holdout, or signed-receipt gates.

| Gate | Current evidence | Required activation evidence |
| --- | --- | --- |
| Proof-stage scope | The next epoch's judge-owned prepared-request boundary is specified in [`PROOF_STAGE_EPOCH.md`](PROOF_STAGE_EPOCH.md). Six Cairo PIE diagnostic proof stages are retained at 1.17–1.95 s; their 6.90–9.78 s full-command times include ingress. The trusted adapter and fold/pipeline proof-stage timers do not exist yet. | Implement the new epoch across all ten cases with withheld inputs and judge-owned timing, qualify its memory interval, re-run baselines, and align judge and website before launch. |
| Contract and data | `check_data.py` verified all 60 public files after transfer to the healthy H200 pod; contract CI also passes. | Repeat the full hash check on the eventual trusted runner. |
| Independent verifiers | Both pinned Rust verifiers were built on Linux and accepted all relevant Cairo proofs in two direct H200 rounds; executable hashes are recorded in [`data/reports/`](../data/reports/README.md). | Build both verifiers from the pinned baseline on the trusted runner and run them inside the judge. |
| Public PIE output files | All six PIEs passed two direct H200 rounds with exact proof hashes and pinned Rust verification; see [`data/reports/`](../data/reports/README.md). | Repeat inside the trusted H200 judge to qualify isolation and ranked timing. |
| Eight-leaf CUDA fold | The two- and eight-leaf CUDA folds passed two direct H200 rounds, each with exact proof, outputs, and packed root hashes. Both two-leaf end-to-end pipeline modes also passed with Rust-verified Cairo leaves. | Repeat the fold and full pipeline inside the trusted H200 judge. |
| Private holdout | A separate 18-case manifest passes hash preflight locally; it is not in Git. | Mount private fixtures read-only on the judge; qualify its PIE, fold, and full-pipeline cases with the pinned verifiers. |
| Scoring | Three tracks, guards, ABBA scheduling, A/A dispersion, and bootstrap checks are covered by local scorer tests. Two unpaired baseline-only H200 rounds are recorded as diagnostics. | Capture a fresh baseline and three valid paired H200 rounds on the same exclusive host; inspect variance and device-memory samples. |
| Intake and dispatch | The intake, trusted builder, tiered receipts, one-active-job dispatcher, exact-run claim, persistent intake limit, conservative rolling GPU budget, and detached Ed25519 signing path pass local tests. The daily PR collector freezes labeled PR heads and records submission IDs; the exporter and website build verify signed receipts before publication. | Configure the dedicated self-hosted runner, workflow variables, GPU budgets, and queue operations. Provision an external operator key, publish its authenticated public half, and run one source-only submission through smoke, qualify, and rank. The internal daily batch needs no always-on intake service. |
| Candidate isolation | The Docker/NVIDIA launcher stages case-only inputs and runtime assets and sanitizes the pipeline manifest. Hosted Linux [CPU probe #36923616450](https://github.com/teddyjfpender/stwo-cuda-challenge/actions/runs/36923616450) passed all eleven filesystem, network, PID, token, output, and forced-ENOSPC checks as UID 65532. A 2 GiB fixed-size per-case output filesystem and 64 MiB judge-side stdout cap are implemented; [`ISOLATION.md`](ISOLATION.md) defines the boundary. The available H200 research pod lacks Docker and mount privileges. | Use an H200 host with Docker/NVIDIA and mount privileges, build the pinned CUDA image, then qualify GPU access, quota, and the launcher with denied-access probes and valid PIE, fold, and pipeline proofs inside it. |

The operator builds assets with `./setup.sh --build`, hashes public fixtures
with `python3 scripts/check_data.py`, and uses `harness/run_arm.py --preflight`
against the private manifest before spending GPU time. The workflow's required
variables are listed in `.github/workflows/h200-rank.yml`; do not put private
paths, credentials, or holdout identifiers into this repository. The
`service/dispatch.py --dry-run` command checks a trusted build and tier gates
without reserving or launching a GPU job.
`python3 service/activation.py --repository OWNER/REPO` checks the live GitHub
runner and required variable names without displaying their values. A real
`service/dispatch.py` call performs this check before creating a workflow run.

Public release comes after these gates, with a reviewed contract epoch and a
fresh baseline score. Existing historical timings in the prover repository
are diagnostic evidence, not score denominators.
