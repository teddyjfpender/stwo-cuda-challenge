# Composed H200 Cairo and circuit CUDA candidate

## Bottleneck and hypothesis

The accepted frontier spent 5.37 s in ingress and 1.96 s in proof execution/decode for the largest public PIE, within an 8.12 s command. The immutable 2.17 GB preprocessed artifact was validated, transposed in host memory, and uploaded during cold proofs. Nsight also showed 216 ms in mixed Blake2s leaf construction and over 450 ms in number-to-bit-reversed FFT kernels on that PIE.

The cumulative hypothesis: permute fixed columns on the GPU after vectorizable host validation; overlap captured-input hashing with parsing while retaining the independent path freshness hash; reuse a verified fixed device image within distinct multi-leaf batches; simplify FFT twiddle offsets and warp barriers; compress complete non-final Blake2s blocks directly from registers; and retain authenticated circuit-static columns and twiddles across successive reductions. Predicted effects were a material cold-PIE command reduction, a further reduction in the multi-node fold's proof stage, unchanged single-PIE peak, and a 2.17 GB capacity cost when the Cairo batch image is enabled. These changes compose in one patch.

## Changed source and mechanism

The patch applies to pinned stwo-zig commit b2873365dc28ed4bc4b27de10e01ea0beeef7c93 and includes the accepted frontier (challenge PR #6 and upstream stwo-zig PR #205). New work in this candidate:

- `src/backends/cuda/native/transform/lde.cu` and `src/backends/cuda/runtime/stages/transform.zig`: exact in-place SIMD-block permutation of a fixed column through a checked mode of the existing transform ABI. One writer owns each exchanged index pair.
- `src/integrations/cairo_cuda/executor/preprocessed_cache.zig`: full-column invalid-M31 flag in a vectorizable pass, followed by upload and GPU permutation for columns above log 16. SHA-256 still authenticates the original artifact bytes.
- `src/integrations/cairo_cuda/canonical_input.zig`: join an owned-byte hashing worker with parsing, retaining the independent second path hash after parsing.
- `src/products/cairo_cuda/app.zig`: default to the previously verified fixed device image for a distinct multi-leaf borrowed-runtime batch. `STWO_CAIRO_CUDA_STATIC_IMAGE=0` disables this capacity-for-latency choice.
- `src/backends/cuda/native/transform/n2b_fused.cuh` and `b2n_fused.cuh`: exact closed-form twiddle offsets replace per-thread loops; register-only warp shuffles no longer have a redundant preceding `__syncwarp`.
- `src/backends/cuda/native/commitment/progressive.cu`: load and compress complete non-final 16-word mixed leaves directly; keep the final block pending for Blake2s's final-block flag.
- `src/integrations/circuit_cuda/resident_memory_plan.zig` and `resident_prover.zig`: retain the authenticated preprocessed columns and forward/inverse twiddles through proof assembly. Key one prepared circuit arena by physical placement, geometry, preprocessed root, and the source object's identity. On a same-circuit hit, skip repeated immutable uploads and CPU twiddle generation while still uploading every dynamic value, circuit hash, and proof header and clearing the proof bundle. Reuse is enabled by default for a borrowed process runtime; `STWO_CIRCUIT_CUDA_STATIC_RESIDENT=0` and `STWO_CIRCUIT_CUDA_REUSE_ARENA=0` allow isolated measurements. A geometry or identity miss evicts the old circuit arena before allocating a new one.
- `src/products/cairo_cuda/app.zig`: evict a preceding circuit arena when the next Cairo leaf needs a different prepared arena. This prevents simultaneous 39 GB Cairo and 28 GB circuit workspaces in the integrated batch.

The cumulative patch also carries accepted-frontier source preparation, fixed-asset prefetch, batch ingress, and publication work under `src/integrations/cairo_cuda/canonical_source.zig`, `executor/ingress/controller_bundle.zig`, `src/products/cairo_cuda/ingress_jobs.zig`, `publication.zig`, and `src/products/circuit_recursion_cuda/main.zig`. No CPU, Metal, Rust, security, fixture, judge, or reference-output source is modified.

## Exploration and rejected variants

- A new exported CUDA transform symbol failed the kernel-closure gate. The accepted design uses a checked mode of the existing ABI and passes that gate.
- A 128-thread Cairo AIR launch showed no measurable proof-stage gain and was removed.
- Halving Cairo AIR code-generation slices from 16 to 8 roots passed exact proofs but raised the large-PIE proof stage from about 1.885 s to 1.931 s in an interleaved A/B/B/A check and raised sampled peak by 212 MB. It was reverted before capture.
- Source lookahead alone did not improve the integrated two-leaf command in a focused test and remains opt-in.
- A Karatsuba QM31 multiplication variant passed arithmetic parity but changed generated CUDA AOT keys, which were not present in the pinned authenticated circuit archive. The exact H200 fold failed at CUDA module lookup, so the variant was fully reverted. Its large-PIE proof-stage timing was also flat. An `__umulhi` M31 microbenchmark gave no meaningful gain and was rejected.
- The [bounded trace and lookup architecture](https://github.com/teddyjfpender/stwo-cuda-challenge/discussions/16) targets the main VRAM opportunity: trace evaluations, coefficients, and Merkle hashes remain live through AIR/OODS/opening. It requires exact replay or streaming across transcript barriers. This candidate does **not** claim that modeled memory saving or a 50% peak reduction.

## Earlier composed-frontier H200 evidence

These measurements describe the earlier candidate in PR #17 relative to the accepted frontier on the preceding H200 pod. They show the cumulative PIE and pipeline improvements inherited by the present patch, not an incremental effect of the new circuit cache. One exclusive H200 SXM, Zig 0.15.2 ReleaseFast, CUDA 12.8, sm_90. Each arm used a fresh process per case and a warmed fixture page cache. The direct qualifier timed adapted-input to published proof/process exit, sampled whole-device NVML peak, recorded reported ingress and proof-stage time separately, checked canonical proof/output/root digests, and invoked the pinned independent Rust Cairo verifier for standalone PIEs and registry leaves. Three interleaved full-basket passes per arm were ordered candidate/baseline/baseline/candidate/baseline/candidate. Times below are medians of three runs; device bytes are decimal GB. All ten candidate cases passed exact digest/output checks in all three passes.

| Public case | Frontier command s | Candidate command s | Change | Frontier ingress s | Candidate ingress s | Frontier proof stage s | Candidate proof stage s | Peak GB frontier → candidate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| PIE 15582797 | 6.221 | 5.471 | -12.1% | 4.288 | 3.604 | 1.281 | 1.242 | 90.484 → 90.484 |
| PIE 15603744 | 6.323 | 5.673 | -10.3% | 4.496 | 3.853 | 1.229 | 1.190 | 89.712 → 89.712 |
| PIE 15581148 | 6.022 | 5.372 | -10.8% | 4.213 | 3.613 | 1.182 | 1.144 | 84.544 → 84.544 |
| PIE 15590913 | 6.773 | 5.922 | -12.6% | 4.509 | 3.698 | 1.556 | 1.510 | 105.214 → 105.214 |
| PIE 15588777–15588780 | 8.124 | 6.673 | -17.9% | 5.374 | 4.047 | 1.959 | 1.889 | 134.071 → 134.071 |
| PIE 15591789 | 6.723 | 6.022 | -10.4% | 4.384 | 3.684 | 1.682 | 1.632 | 116.253 → 116.253 |
| Two-leaf wrap/fold | 2.569 | 2.518 | -2.0% | — | — | 0.543 | 0.533 | 29.419 → 29.419 |
| Eight-distinct-PIE fold | 8.075 | 8.074 | ~0.0% | — | — | 3.526 | 3.495 | 29.419 → 29.419 |
| Two-leaf root pipeline | 17.084 | 15.833 | -7.3% | 7.836 | 6.432 | 1.715 | 1.706 | 69.447 → 69.447 |
| Integrated two-leaf batch | 12.429 | 11.027 | -11.3% | 5.261 | 3.804 | 1.452 | 1.430 | 41.293 → 43.440 |

Pipeline ingress columns are sums of Cairo leaf reports; pipeline proof-stage columns are circuit-resident stages. They do not partition the full command. The fold column also reports the circuit-resident stage. The median paired-ratio diagnostic under the published family weights gives `R_T=0.9213` and `R_M=1.0085`, equivalent to about 8.5% higher latency-track and 3.7% higher balanced-track values **if** these direct measurements were scored. They are not ranked: this host did not run the pinned sandbox, private holdouts, A/A calibration, or signed judge. The integrated batch image costs 2.147 GB (5.2%) peak; every other sampled case peak is unchanged. The memory-track diagnostic worsens. The largest PIE proof stage remains about 1.89 s, above the earlier sub-second target.

Focused Nsight comparison of the large PIE after the proof-kernel edits: mixed-leaf GPU time 216.0 → 167.4 ms (22.5% less for that kernel), n2b-continue<3> 344.6 → 333.4 ms, n2b-final-warp 112.1 → 101.7 ms. Proof execution/decode changed 1.958 → 1.886 s in the focused check. Profiler-instrumented command time is not used as a performance claim.

## Incremental circuit-cache H200 evidence

A second H200 SXM pod ran the saved PR #17 executables against this patch's final executables. All six full-basket passes used the same pod and warmed public fixture cache, with three saved-frontier and three final-candidate passes interleaved. The first saved-frontier pass overlapped a CPU-only build; the other five passes ran after the build, and the GPU was exclusive throughout. Times below are per-case medians of three fresh processes per arm. The proof-stage column is Cairo `proof_execute_and_decode_ns` for PIEs and the sum of circuit-resident stages for folds/pipelines; the full-command column is external adapted-input to published-proof/process-exit wall time. The two boundaries must not be combined. Whole-device NVML peaks are decimal GB.

| Public case | PR #17 command s | Final command s | Change | PR #17 proof stage s | Final proof stage s | Change | Peak GB, both |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| PIE 15582797 | 5.772 | 5.771 | ~0% | 1.256 | 1.254 | -0.2% | 90.470 |
| PIE 15603744 | 5.722 | 5.822 | +1.8% | 1.204 | 1.205 | +0.1% | 89.698 |
| PIE 15581148 | 5.622 | 5.671 | +0.9% | 1.156 | 1.155 | ~0% | 84.531 |
| PIE 15590913 | 6.072 | 6.072 | ~0% | 1.531 | 1.533 | +0.1% | 105.200 |
| PIE 15588777–15588780 | 7.073 | 6.923 | -2.1% | 1.910 | 1.906 | -0.2% | 134.057 |
| PIE 15591789 | 6.273 | 6.273 | ~0% | 1.656 | 1.658 | +0.1% | 116.240 |
| Two-leaf wrap/fold | 2.718 | 2.718 | ~0% | 0.550 | 0.544 | -1.0% | 29.405 |
| Eight-distinct-PIE fold | 8.225 | 7.573 | **-7.9%** | 3.499 | 2.838 | **-18.9%** | 29.405 |
| Two-leaf root pipeline | 16.592 | 16.483 | -0.7% | 1.807 | 1.735 | -4.0% | 69.434 |
| Integrated two-leaf batch | 11.277 | 11.377 | +0.9% | 1.404 | 1.437 | +2.4% | 43.427 |

All 30 final-candidate case runs passed exact canonical proof/output/root hash checks; pinned independent Rust Cairo verification accepted every applicable standalone PIE and registry leaf. The direct qualifier does not invoke an independent circuit verifier; the exact recursive proof bytes and canonical outputs matched. The fixed circuit arena planned 28,132,569,632 bytes versus 28,132,566,560 bytes before (3,072 extra bytes); its sampled whole-device peak was unchanged. On a focused eight-leaf comparison, setting `STWO_CIRCUIT_CUDA_STATIC_RESIDENT=0` returned circuit time to 3.926 s from 2.940 s with reuse enabled in that pair, corroborating the cache mechanism. The paired full-basket measurements above are the primary claim.

The provisional integrated build retained a 28 GB circuit arena while allocating the next 39 GB Cairo arena, raising sampled peak from 43.427 to 71.143 GB. The final Cairo handoff evicts the mismatched arena before allocation; three final full-basket passes measured the original 43.427 GB peak. This fixes a composition regression; it is not a memory reduction relative to PR #17. Median regressions up to 2.4% in unchanged single-node cases are within the observed full-command variation and are reported rather than hidden. The largest PIE proof stage remains about 1.91 s and the patch does not achieve a 50% basket-wide speed or memory reduction.

## Proof checks, limits, and attribution

`python3 challenge.py check-data` passed all 10 cases/60 files. The final H200 `python3 challenge.py setup --build` passed, including source and patch attestation; the active CUDA closure remained 147 symbols with 0 staged. `python3 challenge.py capture` validated derivative manifests and emitted the 65,253-byte cumulative patch, which applies to the original pin. `zig build check-cairo-cuda-local -Doptimize=ReleaseFast`, `zig build test-cairo-cuda-local -Doptimize=ReleaseFast`, Zig formatting, and `git diff --check` passed after the final source changes. The required `python3 challenge.py benchmark --tier smoke --track balanced` was attempted, but the runner refused to start because this research pod has no pinned SHA-256 sandbox image. Direct qualification instead checked every public case three times per arm. The direct qualifier does not invoke an independent circuit verifier; recursive proof bytes and canonical output/root/packed digests matched the pinned references exactly. Rust Cairo verification passed for the standalone and registry-leaf proofs.

Final candidate binary SHA-256 on the second pod: Cairo `d1035a53b39cc3bc3bb0538159204c96b0c9d53f3469bf07da0bbacbb40ffe4c`, recursion `746a0b8d64df99911e5d418eb53a011bcac2072088ee0cdfcb4791ee6a5067e4`. Saved PR #17 binary SHA-256 on that pod: Cairo `94e05cd095811697d4996f534cf24da2e427805c013ac6959d72158592042643`, recursion `bcc38472db0762796365a566f6862ef4ca4de18592add5ebd50a99fbb8941ecb`. Preparation/build time is excluded from command times.

The next substantial speed and capacity changes are bounded trace-evaluation/lookup materialization with exact decommit replay and a reusable value-generation template or parallel sibling CPU circuit builds feeding serialized or independently scheduled CUDA proofs. Nsight measured about 1.8 s of GPU kernels in the largest PIE's roughly 1.9 s proof stage, so a sub-second PIE needs a major algorithmic reduction across FFT, AIR, and commitment work rather than launch housekeeping. In the eight-leaf fold, about 4.3 s of the 7.1 s tree reduction is outside the measured circuit-resident stage, much of it per-node circuit-value construction; GPU cache work alone cannot halve the full command. These designs are tracked in [Discussion #16](https://github.com/teddyjfpender/stwo-cuda-challenge/discussions/16), its [architecture follow-up](https://github.com/teddyjfpender/stwo-cuda-challenge/discussions/16#discussioncomment-18719294), and the [new measured cache follow-up](https://github.com/teddyjfpender/stwo-cuda-challenge/discussions/16#discussioncomment-18724084); the future designs are not claimed as implemented here. Challenge [PR #11](https://github.com/teddyjfpender/stwo-cuda-challenge/pull/11) independently explores a fixed device image, and [PR #13](https://github.com/teddyjfpender/stwo-cuda-challenge/pull/13) independently explores vectorized M31 validation; their overlap is acknowledged.

Model/harness attribution: OpenAI Codex (GPT-6) through the Codex tool harness, directed by Theodore Pender. Public fixture, challenge, and source contributions are credited to their respective repositories. No private fixtures, proof blobs, logs, or binaries are included in the PR.

## Submission

The review PR containing this patch is the operator's review surface. The operator controls any `ready-to-judge` label; opening a PR does not itself create a ranked receipt.
