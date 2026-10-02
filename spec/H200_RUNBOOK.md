# H200 operator runbook

This runbook is for the public staging challenge. The local contract checks
pass, but no H200 judge runner is registered yet. Do not dispatch a judged
submission until the live activation gates in [`ACTIVATION.md`](ACTIVATION.md)
are satisfied. A single H200 is reserved for one run at a time; all CPU builds,
fixture transfers, and hash checks happen before its timed proof work.

On a restricted GPU pod without Docker and mount privileges, run
`python3 scripts/qualify_direct_h200.py --out /external/direct-runs` after
`./setup.sh --build` to check every public CUDA proof and recursive root against
its pinned digest and independent Cairo verifiers. Each case writes elapsed
time, 10 ms sampled peak device memory, and its backend report. This is
**direct, unsandboxed diagnostic evidence only**: it does not exercise the
trusted judge's output quota, network isolation, Docker image, signed receipt,
or paired A/B scoring. Keep generated proofs and logs outside Git and do not
use these numbers as ranked scores. Use `--case-id ID` to narrow a smoke run.

## Keep the research loop short

Use an H200 network volume or other persistent filesystem for the verified
fixture store, source checkouts, `.cache` (including the 2.17 GB canonical
preprocessing asset and compiled Rust verifiers), Zig/CUDA toolchains, build
cache, and external run journals. A pod's ephemeral root filesystem is not the
cache: stopping or replacing a pod can lose twenty minutes or more of rebuild
and transfer work. Mount the volume at the **same path** on replacement pods,
then recheck pinned hashes; persistence does not make a file trustworthy. Keep
credentials and private fixtures outside public worktrees. Prepare and build
before reserving expensive proof time where the provider permits CPU setup.
Do not rely on a particular stopped pod restarting: H200 capacity can be
unavailable. Keep the same persistent volume mountable by a fresh compatible
pod. Preserve one active experiment journal outside Git and never run a second
build or proof on the measurement GPU during an A/B comparison.

Before the first proof, run one of these checks. Both verify Zig 0.15.2,
nvcc/Cargo availability, the pinned source and runtime files, staged AIR
bundles, canonical preprocessing hash, executable/verifier hashes, selected
fixture hashes, H200 capacity, and idle whole-device usage. The judge check
also fails early if Docker, its exact pinned image, output-image mount
capability, or the filesystem/network/quota isolation probe is missing.

```sh
python3 scripts/h200_preflight.py --mode direct --source workspace/baseline \
  --out /external/runs/baseline-preflight.json
python3 scripts/h200_preflight.py --mode judge --source workspace/baseline \
  --image "$STWO_SANDBOX_IMAGE" --out /external/runs/judge-preflight.json
```

The first command is for a restricted Runpod research pod; its success does
not qualify the sandbox or permit ranked results. If the second command fails,
fix that host/image before invoking `harness/run_arm.py` or dispatching smoke.
The preflight receipt labels itself `prerequisites-only`. It is deliberately
separate from both exact proof qualification and a signed judge receipt.

For each hypothesis, name the expected stage and fractional gain. Compile the
touched Zig/CUDA target and run the relevant local test first. Then use the
direct A/B driver on an otherwise idle H200; it interleaves baseline and
candidate twice for one representative PIE and one fold or pipeline case.
Each run checks canonical proof hashes and the pinned verifiers and appends a
durable JSONL row with exact source commit, tracked diff/untracked source and
executable hashes, cold full-command time, available ingress/proof phases,
whole-device peak, proof hashes, and verification flags. A stage-gain gate
keeps a weak idea from triggering the full ten-case basket. For example:

```sh
python3 scripts/h200_experiment.py --baseline workspace/baseline \
  --candidate workspace/stwo-zig --out /external/runs/source-cache-01 \
  --hypothesis 'overlap fixed-asset loading with source preparation' \
  --stage ingress_ns --min-stage-gain 0.05 \
  --max-companion-regression 0.05 --full-if-promising
```

For a recursion or pipeline hypothesis, select that case with
`--smoke-companion` and also set `--target-case` to the same ID. The PIE then
acts as the full-command regression guard. The gate always tests the declared
stage on the chosen target and full-command time on the other case.

`experiment.json` records preflight/build identities and the stated timing
boundary; `runs.jsonl` survives a later failure; `gate.json` says whether the
full basket was admitted. Use a fresh output directory for every experiment.
The full basket is one paired diagnostic pass by default; choose more rounds
explicitly when variance matters. Its output remains unsandboxed and unranked.
Candidate-reported ingress and proof timers are diagnostic; an editable prover
can change them. The externally measured cold command and NVML peak remain the
comparable values. Record **preparation**, **cold adapted-input to published
proof**, and **warm proof** as different quantities. This driver times only
the cold command; it labels warm proof `not measured` because a resident
request protocol and judge-owned timer do not yet exist. Package creation,
fixture transfer, and compilation cannot silently move before the `h200-v1`
clock or become a proof-stage rank; changing that boundary requires the
reviewed next epoch in [`PROOF_STAGE_EPOCH.md`](PROOF_STAGE_EPOCH.md).

## Prepare the host once

1. Use one exclusive H200 SXM with the device capacity in `benchmark.json`.
   Install Zig 0.15.2, CUDA/nvcc, Cargo, `nightly-2026-01-15`, Git LFS,
   OpenSSL with Ed25519 support, Docker Engine, the
   [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html),
   GitHub CLI, `e2fsprogs`, and `util-linux`. The judge process must run as
   root or have passwordless `sudo` for mounting, unmounting, and chmod on its
   own 2 GiB per-case ext4 output images. Keep service state,
   private fixtures, credentials, and the
   2 GiB canonical preprocessing asset outside this repository.
   `./setup.sh --build` resolves the explicit pinned CUDA build options from
   `nvcc`, `g++`, `ar`, and the toolkit's `lib64`, targeting SM 90. Set
   `STWO_CUDA_NVCC`, `STWO_CUDA_HOST_CXX`, `STWO_CUDA_AR`, `STWO_CUDA_HOME`,
   `STWO_CUDA_LIBRARY_DIR`, or the host runtime path overrides if auto-detection
   differs; `STWO_CUDA_BUILD_JOBS` defaults to four.
   Setup stages the pinned Cairo AIR library, every digest-declared AIR bundle,
   witness programs, topology, and fixed/relation tables under
   `.cache/cuda-artifacts`. The sandbox separately stages their read-only source
   copies because the pinned AOT binder also opens one library relative to its
   working directory; the candidate runs from `/candidate` with explicit
   writable output paths under `/work`.
2. Clone the challenge, then run `git lfs pull`, `./setup.sh --build`, and
   `python3 scripts/check_data.py`. This fetches the pinned prover, builds the
   baseline and local-workspace CUDA products and both pinned Rust verifiers,
   generates the canonical preprocessing asset, and checks every public file.
   The baseline and
   candidate source roots and binary hashes must match their build
   attestations before ranking.
   Build `harness/sandbox.Dockerfile` from an NVIDIA CUDA runtime base pinned
   by repository digest:

   ```sh
   docker build -f harness/sandbox.Dockerfile \
     --build-arg CUDA_RUNTIME_IMAGE='nvidia/cuda:VERSION-runtime-ubuntu24.04@sha256:BASE_DIGEST' \
     -t stwo-judge:h200-v1 .
   ```

   Replace the placeholders with the qualified CUDA runtime version and full
   base digest. Record the local image ID returned by
   `docker image inspect --format '{{.Id}}' IMAGE_TAG`. Set
   `STWO_SANDBOX_IMAGE` to that `sha256:` ID. The judge refuses a mutable tag
   or an image absent from the local daemon. First run
   `python3 scripts/probe_sandbox.py --image "$STWO_SANDBOX_IMAGE"` on the host.
   Verify the exact image and driver
   combination with one sandboxed PIE, fold, and full-pipeline proof before
   ranking; local plan tests alone do not qualify it.
3. Copy the separately held ranked fixture store and manifest to read-only
   judge-owned paths. Check every digest before the H200 proof loop:

   ```sh
   python3 harness/run_arm.py --source workspace/baseline \
     --fixtures "$STWO_FIXTURE_ROOT" --manifest "$STWO_RANKED_MANIFEST" \
     --preprocessed .cache/preprocessed-canonical.bin \
     --artifact-dir .cache/cuda-artifacts \
     --cairo-verifier .cache/rust-official/release/stwo-cairo-official-verifier \
     --out .runs/preflight --round 0 --preflight
   ```

   Never put private case names, expected digests, or fixture paths in GitHub
   Discussions or a submission repository.
4. Generate an Ed25519 operator key outside this repository and service state,
   readable only by the judge identity. Publish its public half through an
   authenticated channel and retain the public-key digest for this epoch.
   `openssl genpkey -algorithm ED25519 -out /secure/path/operator-key.pem` and
   `openssl pkey -in /secure/path/operator-key.pem -pubout -out operator-public.pem`
   generate the key pair; restrict the private file to mode `0600`.
   Configure `STWO_RECEIPT_SIGNING_KEY` with the private-key **path**, not key
   bytes. The publisher signs the exact receipt JSON and serves a detached
   signature; verify it with `python3 service/receipt_signature.py --receipt
   RECEIPT.json --signature RECEIPT.signature.json --public-key operator-public.pem`.
   Candidate sandbox qualification must precede use of the key on an H200 job.
5. Register one online self-hosted runner with the default `self-hosted` label
   and `h200-stwo-challenge`. Configure all ten repository variable names
   used in `.github/workflows/h200-rank.yml` with nonempty paths. Run
   `python3 service/activation.py --repository OWNER/REPO`; it prints no
   variable values and must pass before dispatch. Qualify process isolation,
   outbound-network blocking, read-only fixture mounts, and receipt signing
   separately before opening the public leaderboard. The required access
   matrix and denied-access probes are in [`ISOLATION.md`](ISOLATION.md).

## Qualify the exact workflow

1. For the internal daily batch, review challenge PRs and label accepted heads
   `ready-to-judge`. Run `python3 service/pr_batch.py --dry-run`, then
   `python3 service/pr_batch.py --source workspace/baseline --state /operator/state`
   to record each PR number, exact SHA, and submission ID. Build those IDs with
   `service/build_worker.py`. No HTTP service or participant key is required.
   The optional `service/intake.py` endpoint can instead accept a source commit
   on loopback with an explicit `--max-intake-requests-24h` limit. Uploaded
   binaries are not run by the ranked judge; the worker rebuilds the pinned
   source plus allowed patch outside the H200 timing interval.
2. Dispatch `smoke`, then `qualify`, then `rank` through
   `service/dispatch.py`, passing `--max-gpu-minutes-24h` and
   `--max-repository-attempts-24h` on each live call. For example, `540` and
   `3` allow at most six 90-minute reservations globally and three attempts
   from one repository in any rolling day. Failed and cancelled attempts count
   conservatively. Each tier requires the prior receipt. The workflow checks
   out the event's exact commit and atomically claims its dispatch against the
   first GitHub run ID before measuring one exclusive H200,
   verifies every proof and root, and publishes a redacted receipt. The rank
   tier performs three paired ABBA rounds and writes all eligible score files
   from the same measurements.
3. Inspect the complete judge-owned evidence, the public redacted receipt,
   per-case time and memory ratios, A/A dispersion, bootstrap intervals, and
   peak device-memory samples. Run the public and private baskets against the
   pinned baseline first; no historical H100/H200 time is a score denominator.
   If a claimed workflow was cancelled before receipt publication, run
   `service/reconcile.py` so the exact completed GitHub run releases its
   dispatch slot. An unclaimed attempt or a run not yet visible in GitHub
   stays reserved for operator review.
4. Verify and export reviewed rank receipts with `service/site_export.py` as
   documented in [`OPERATIONS.md`](OPERATIONS.md). Commit the generated
   scorecards, redacted receipts, signatures, and public key to the website
   repository; its build rechecks every signature. Keep the website in staging
   until the proof-stage epoch and H200 activation gates are qualified.
5. Shut down the paid H200 host when proof qualification is complete. Retain
   immutable evidence and signed receipts in the external service store. Keep
   generated proofs and logs outside Git. Public reference outputs are already
   under `data/outputs` and are checked by `scripts/check_data.py`.
