# Precompute nonce-independent Blake2s PoW work

Research candidate against `b2873365dc28ed4bc4b27de10e01ea0beeef7c93`.
No ranked result, signed receipt, or live intake submission is claimed.
The narrow PoW stages improved, but total proving time showed no established
win and PIE whole-command times regressed. This is a research candidate, not
a demonstrated full-command latency improvement.

## Bottleneck and mechanism

The CUDA PoW search repeatedly hashes a fixed 32-byte prefix followed by an
8-byte nonce. In Blake2s round zero, all four column G operations depend only
on the prefix. Three diagonal G operations consume zero message words and
also remain independent of the nonce. Those three diagonal operations have
disjoint state from the fourth, nonce-dependent G(8, 9).

Compute these seven G operations once per block, publish the resulting state
in shared memory, synchronize, and start each candidate with G(8, 9), followed
by the original remaining nine rounds. This preserves the complete hash,
plain/M31 output policies, nonce lattice, search order, atomic minimum, and
fixed security profile. No witness, proof, fixture, or nonce is cached across
requests. The CuMetal implementation is unchanged.

Changed paths (relative to the pinned prover):

- `src/backends/cuda/native/pow/candidate.cuh`: prepared prefix and hash entry.
- `src/backends/cuda/native/pow/search.cu`: prepare the block-shared prefix.
- `src/integrations/circuit_cuda/native/circuit_grind.cu`: use the same prepared
  prefix in the device kernel and its host emulation.
- `src/integrations/circuit_cuda/tests/grind_regression.py`: reproducible
  focused GPU/oracle checks and optional paired grind-call measurements.

Prediction: reduce arithmetic in long PoW searches, with little benefit for
short searches. End-to-end benefit is limited by the fraction of each proof
spent grinding. Arena sizes and device allocations should remain unchanged.

## Focused evidence

One NVIDIA H200 SXM, SM 90, driver 570.124.06, CUDA 12.8, Zig 0.15.2.
The GPU passed an initial computation check and had no other compute users.

The focused test uses 15 fresh prefixes per width/channel and ABBA ordering
within each prefix, giving 30 observations per arm. Each paired ratio divides
the mean of the two candidate observations by the mean of the two baseline
observations for that same prefix; the table gives the median of 15 ratios.
All compared nonces matched. Timings cover the synchronous circuit grind call,
including allocation, copies, kernel work, synchronization and teardown.
They are neither proof-stage times nor full prover command times.

| Channel | Bits | Candidate/baseline paired time ratio |
| --- | ---: | ---: |
| Plain | 8 | 0.9970 |
| Plain | 20 | 0.9718 |
| Plain | 24 | 0.9348 |
| Plain | 26 | 0.9304 |
| M31 | 8 | 0.9968 |
| M31 | 20 | 0.9790 |
| M31 | 24 | 0.9361 |
| M31 | 26 | 0.9321 |

Focused correctness checks:

- 50 comparisons against an independent Python `hashlib.blake2s` oracle,
  including both output formats, short/partial search windows, no-winner
  cases, and a window crossing the 20-bit low-nonce boundary: passed.
- NVIDIA Compute Sanitizer memcheck on those 50 checks: zero errors.
- Existing circuit `test-cuda-device`: 6/6 passed, including Rust Stwo
  known answers, CPU sweeps, production-width fresh transcripts, provider
  handoff and invalid-width rejection.
- Capture, derived CUDA manifest verification, clean-baseline patch
  applicability and whitespace checks: passed.

`ptxas` reports 40 registers and 96 bytes shared memory per circuit search
block, versus 38 registers and 32 bytes for baseline; neither spills. Both
retain the original 256-thread blocks, 1024-block grid and launch bound of six
blocks per multiprocessor. The extra 64 bytes are block-local shared memory,
not an additional resident device allocation.

Inspection of the integrated recursion executable with `cuobjdump` shows a
separate backend-search tradeoff: both builds use 40 registers, while the
candidate has a 40-byte stack frame (baseline: zero) and 1120 bytes of shared
memory (baseline: 1056). The full public runs below measure the resulting
behavior; the circuit microbenchmark's no-spill result must not be generalized
to the integrated backend kernel.

Reproduce from the challenge root on an H200 after setup:

```sh
python3 workspace/stwo-zig/src/integrations/circuit_cuda/tests/grind_regression.py \
  --baseline workspace/baseline --repetitions 15
compute-sanitizer --tool memcheck --error-exitcode 86 \
  python3 workspace/stwo-zig/src/integrations/circuit_cuda/tests/grind_regression.py
zig build --build-file workspace/stwo-zig/src/integrations/circuit_cuda/build.zig \
  test-cuda-device -Doptimize=ReleaseFast -Dcuda-nvcc=/usr/local/cuda/bin/nvcc \
  -Dcuda-library-dir=/usr/local/cuda/lib64 -Dcuda-arch=90 --summary all
```

## Public proof and command measurements

`python3 challenge.py setup --build` completed on the H200. Both requested
`benchmark --tier smoke --track balanced` and `--tier qualify --track balanced`
commands exited 2 at the pinned sandbox-image preflight. No judge gate was
bypassed or modified. Validation therefore used the repository's documented
`scripts/qualify_direct_h200.py` helpers, explicitly **direct, unsandboxed and
unranked**. No private holdout or ranked isolation check was run.

The first PIE and two-leaf fold passed direct smoke checks on both builds.
Then every one of the ten public cases ran in three per-case ABBA rounds
(baseline, candidate, candidate, baseline): **six observations per build per
case, 120 case commands total**, with no discarded samples. All canonical
checks passed. The 72 standalone Cairo proofs passed the pinned official Rust
verifier; the 48 pipeline Cairo leaves passed the pinned registry Rust
verifier. Recursive and pipeline root proof/output/packed hashes matched the
published references. Cairo reports retained the canonical security profile,
NVIDIA provider and zero CPU proving fallbacks.

The following values are medians of six observations. Memory is the **maximum
of the six whole-command peak measurements**, sampled by NVML every 10 ms.
B means baseline; C means candidate. This is not a score table.

| Public case | Execute/finish seconds B / C | Whole-command seconds B / C | Maximum peak bytes B / C |
| --- | ---: | ---: | ---: |
| `pie:15582797_15582797` | 1.2835 / 1.2819 | 7.550 / 7.624 | 91021180928 / 90470088704 |
| `pie:15603744_15603744` | 1.2335 / 1.2324 | 7.677 / 7.849 | 89698336768 / 89698336768 |
| `pie:15581148_15581148` | 1.1823 / 1.1818 | 7.200 / 7.349 | 84530954240 / 84530954240 |
| `pie:15590913_15590913` | 1.5565 / 1.5570 | 8.175 / 8.425 | 105200484352 / 105200484352 |
| `pie:15588777_15588780` | 1.9578 / 1.9592 | 9.653 / 9.978 | 134057295872 / 134057295872 |
| `pie:15591789_15591789` | 1.6872 / 1.6840 | 8.375 / 8.500 | 116239892480 / 116239892480 |
| `recursion:two-leaf-wrap-fold` | 0.3043 / 0.3040 | 2.744 / 2.718 | 29405216768 / 29405216768 |
| `recursion:eight-distinct-pie-fold` | 2.0833 / 2.0809 | 8.276 / 8.325 | 29405216768 / 29405216768 |
| `pipeline:two-leaf-root` | 1.9349 / 1.9355 | 17.735 / 17.786 | 69433556992 / 69433556992 |
| `pipeline:two-leaf-batch-integrated` | 1.6531 / 1.6513 | 14.532 / 14.532 | 41279291392 / 41279291392 |

Timing boundaries:

- Cairo execute/finish uses the existing `proof_execute_and_decode_ns` field.
  Despite its name, it ends at `proof.finish`, before canonical decoding,
  verification and publication.
- Circuit execute/finish is the existing `resident-phase` log's `schedule_ns`
  plus `finish_ns`. Planning, static hashing, ingress and decoding are excluded.
  For folds/pipelines, the table sums the reported Cairo and circuit intervals.
  It is a diagnostic sum, not a trusted proof-only score or pipeline critical
  path. The two-/eight-leaf folds contain one/seven circuit intervals; each
  pipeline contains two Cairo intervals and three circuit intervals.
- Whole-command time uses the unchanged `harness.run_arm.run` timer, from
  subprocess launch to exit, including product input loading, setup, internal
  verification and publication. The independent Rust checks occur afterward
  and are excluded. The pipeline timer covers its outer Python command.
- The PoW numbers below are Cairo's existing CUDA event interval for its `pow`
  stage, not the focused circuit API timer and not a complete proof timer.

| PIE | Reported PoW device milliseconds B / C | Median paired C/B ratio |
| --- | ---: | ---: |
| `15582797_15582797` | 5.3648 / 5.1495 | 0.9567 |
| `15603744_15603744` | 7.3570 / 6.7225 | 0.9142 |
| `15581148_15581148` | 1.9276 / 1.8403 | 0.9552 |
| `15590913_15590913` | 10.3965 / 9.1252 | 0.8776 |
| `15588777_15588780` | 3.9281 / 3.8201 | 0.9799 |
| `15591789_15591789` | 5.4180 / 5.1138 | 0.9527 |

`MEASUREMENTS.json` retains every numerical observation, timing scopes,
per-round ratios, A/A baseline ratios, source/patch identity, local binary
build records and verifier hashes. Binaries and patch hashes were rechecked
after the run. The capture hash remained
`79b6f902d6d106bf938042ea5153923b575b86e47607cdc22e5059e505756b79`.
Generated proofs, process logs and caches are excluded from this PR.

### Interpretation and regressions

The integrated PIE PoW stage's median paired ratios are 0.8776–0.9799
(about 2.0–12.2% less time), consistent with a narrow arithmetic benefit.
For each ratio, average the two C observations and divide by the two B
observations in the same round, then take the median of three round ratios.
Ratios therefore need not equal ratios of the separately reported medians.

The full execute/finish diagnostic ratios span **0.9984–1.0032** across the
basket. These small changes do not establish an overall proving-time win.
All six PIE **whole-command** paired ratios regressed by **1.0–3.0%**.
The eight-leaf fold regressed by 1.5%, the serial pipeline by 0.3%; the two-leaf
fold improved by 2.7% and integrated pipeline by 0.2%. These are observed
exploratory comparisons, not statistically qualified ranking results.
The command regressions are retained, not attributed to noise or dismissed.
Their cause remains unresolved, and this candidate should not be promoted as
a full-command latency improvement without investigating them. Raw baseline
A/A comparisons and all samples are available for that investigation.

Planned arena sizes are identical for every case. Nine cases also have
identical measured maximum peak memory; the first PIE has one higher baseline
peak. That isolated maximum difference does not establish a memory saving.
The integrated backend's extra stack frame is a concrete resource tradeoff;
this experiment does not establish that it caused the command regressions.

Equivalent public-case reproduction, from the challenge root after setup and
capture on a CUDA host (choose a fresh output directory):

```bash
stwo_research_out=/tmp/stwo-pow-public-research
stwo_case_ids=$(python3 -c 'import json; print("\n".join(c["id"] for c in json.load(open("fixtures/public-v1.json"))["cases"]))')
for round in 1 2 3; do
  for case_id in $stwo_case_ids; do
    step=0
    for arm in baseline stwo-zig stwo-zig baseline; do
      python3 scripts/qualify_direct_h200.py --source "workspace/$arm" \
        --case-id "$case_id" \
        --out "$stwo_research_out/r$round-$case_id-$step-$arm"
      step=$((step + 1))
    done
  done
done
```

The measurement orchestration used the same unchanged `qualify_case` and
NVML helpers in that order, and extracted the existing phase fields described
above. No judge, verifier, scoring or timing implementation was changed.

## Tradeoffs, rejected experiments and attribution

The change adds shared prefix state and serial block initialization. Very
short searches can pay that overhead without amortizing it; focused 8-bit
measurements showed no meaningful improvement. Effects on hardware other than
this H200 are unmeasured.

Two preceding experiments were rejected and are absent from this patch:
warp-sharing the best-nonce atomic read passed correctness but produced
paired ratios around 1.00–1.013; relaxing the six-block launch bound to four
gave no consistent benefit and did not eliminate any baseline spills.

The hypothesis, negative results, and follow-up are in
[Discussion #1](https://github.com/teddyjfpender/stwo-cuda-challenge/discussions/1).
Attribution: OpenAI Codex desktop (GPT-6 family), operated by @adrienlacombe;
focused tests used the included Python/hashlib harness, and public measurement
orchestration reused the unchanged challenge qualification/measurement helpers; the
baseline hash/search implementation and challenge harness are from the pinned
`teddyjfpender/stwo-zig` and `teddyjfpender/stwo-cuda-challenge` repositories.
No CPU, Metal, Rust, security, judge, fixture, or reference-output code was
edited. Local Apple Silicon Zig validation encountered SDK/linker errors;
the successful device checks above ran on Linux/H200 instead.

## Submission

Fork: https://github.com/adrienlacombe/stwo-cuda-challenge
Review branch: `codex/pow-prefix-precompute`.
The review PR records the full immutable fork commit containing this patch,
these notes and `candidate/MEASUREMENTS.json`.
Intake submission ID and signed rank receipt: none; ranked service is staging.
