# Candidate notes: overlap authenticated fixed-asset ingress

## Bottleneck and mechanism

The public `pie:15581148_15581148` H200 baseline spent 5.433 s in Cairo ingress during a 7.280 s full command. Static initialization alone took 2.475 s. A focused profile of the canonical 543,100,528-word fixed coefficient artifact measured 1.942 s reading and hashing, 0.183 s checking canonical words, and 0.282 s reordering SIMD coefficient blocks. Proof execution and decoding took 1.191 s.

Changed pinned prover paths:

- `src/integrations/cairo_cuda/executor/preprocessed_cache.zig`: capture and SHA-256 hash the exact fixed artifact bytes on a worker; parse and upload that captured snapshot with the existing column identity, geometry, canonical-word, and artifact-digest checks.
- `src/integrations/cairo_cuda/executor/ingress/controller_bundle.zig`: pass the optional snapshot into static initialization.
- `src/products/cairo_cuda/app.zig`: start the worker before runtime and dynamic source preparation, join before static loading, and release its allocation after the command.

The hypothesis is that the independent fixed-asset read/hash can run alongside dynamic source preparation and runtime setup, reducing adapted-input-to-publication wall time. The proof algorithm, canonical security parameters, CUDA kernels, and device arena plan are unchanged. This adds a temporary 2.17 GB host allocation for one captured artifact; peak GPU memory is not expected to improve.

## Evidence

Pinned source commit: `b2873365dc28ed4bc4b27de10e01ea0beeef7c93`. Hardware: one NVIDIA H200 per direct run, SM 90, 143,771 MiB device memory. The direct qualification script measures the whole prover command from launch to exit and samples whole-device NVML memory every 10 ms. Cairo `ingress_ns` and `proof_execute_and_decode_ns` come from the candidate's backend report and are separate from that full-command timer. All results below are unranked and unsandboxed research measurements. They are single samples, not a paired score. The full-basket arms below used the same second H200 pod at different times while CUDA builds were also running.

The focused same-host smoke pair on `pie:15581148_15581148` passed the pinned independent Rust verifier and exact canonical proof hash:

| Metric | Baseline | Candidate |
| --- | ---: | ---: |
| Full command | 7.280 s | 5.872 s |
| Cairo ingress | 5.433 s | 3.995 s |
| Static initialization | 2.475 s | 0.943 s |
| Proof execution and decoding | 1.191 s | 1.184 s |
| Whole-device peak | 84,530,954,240 bytes | 84,530,954,240 bytes |
| Planned arena | 82,697,758,816 bytes | 82,697,758,816 bytes |

One direct full public basket pass per arm on the same H200 produced the following diagnostics. Each cell is full-command seconds / whole-device peak GiB. The candidate arm ran before the baseline arm; this is not an ABBA paired measurement, and concurrent builds add variance. The descriptive equal-family geometric mean command-time reduction is 8.7%, not an official score.

| Public case | Baseline | Candidate |
| --- | ---: | ---: |
| `pie:15582797_15582797` | 7.885 / 84.27 | 5.925 / 84.27 |
| `pie:15603744_15603744` | 8.378 / 83.55 | 7.378 / 83.55 |
| `pie:15581148_15581148` | 7.277 / 78.74 | 6.776 / 79.25 |
| `pie:15590913_15590913` | 8.728 / 97.99 | 6.526 / 97.99 |
| `pie:15588777_15588780` | 9.830 / 124.86 | 7.627 / 124.86 |
| `pie:15591789_15591789` | 8.127 / 108.27 | 7.277 / 108.27 |
| `recursion:two-leaf-wrap-fold` | 2.524 / 27.40 | 2.430 / 27.40 |
| `recursion:eight-distinct-pie-fold` | 8.281 / 27.40 | 7.930 / 27.40 |
| `pipeline:two-leaf-root` | 18.646 / 64.68 | 17.792 / 64.68 |
| `pipeline:two-leaf-batch-integrated` | 14.287 / 38.46 | 13.739 / 38.46 |

All six PIEs passed the pinned independent Rust verifier, matched the reference proof SHA-256, and reported the canonical security profile with no CPU proving fallback. Both recursive folds and both pipelines matched the public root, output, and packed hashes; pipeline Cairo leaves also passed Rust verification. The public fixture hash check passed for all 60 files. Focused local checks passed: `zig build check-cairo-cuda-local -Doptimize=ReleaseFast`, `zig build test-cairo-preprocessed-cache -Doptimize=ReleaseFast`, and `zig build test-cairo-cuda-local -Doptimize=ReleaseFast`. `python3 challenge.py capture` produced a 12,454-byte patch affecting only the three paths above and confirmed CUDA source closure.

On the second pod, the first read of the freshly transferred artifact took 104.5 s in static initialization; warmed runs recovered to normal times. This storage-cold observation is retained as a limitation, not used as an improvement claim. The candidate does not reduce proof-stage time or planned GPU memory. Recursive-only timing changes should be treated as run-to-run variation because this patch does not change their proof path.

## Tradeoffs and discussion

An additional experiment moved validation and SIMD reordering into the worker. Two verified H200 smoke repeats took 6.785 s and 6.827 s versus 6.276 s for the earlier snapshot-only version on that pod; static initialization rose from about 1.0 s to 2.2 s. That change was discarded. The submitted patch retains the faster, smaller snapshot-only design.

The temporary host allocation is roughly the artifact size (2.17 GB). The GPU arena and canonical proof outputs are unchanged. Discussion: [overlap authenticated fixed-asset preparation](https://github.com/teddyjfpender/stwo-cuda-challenge/discussions/5); related [source-ingress geometry discussion](https://github.com/teddyjfpender/stwo-cuda-challenge/discussions/2).

Research and implementation were performed by OpenAI Codex (GPT-6) using the Codex tool harness, directed by Theodore Pender. No other human contributors to this candidate are claimed.

## Submission

[Review PR #6](https://github.com/teddyjfpender/stwo-cuda-challenge/pull/6) links this patch and these notes. GitHub rejected a personal fork because the authenticated account already owns the parent repository, so the review PR uses a branch in the challenge repository. Ranked H200 intake remains in staging; there is no submission ID or signed rank receipt, and these local timings do not establish leaderboard placement.
