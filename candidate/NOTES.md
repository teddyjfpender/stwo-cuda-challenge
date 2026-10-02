# Composed H200 Cairo CUDA candidate

## Bottleneck and hypothesis

The accepted frontier spent 5.37 s in ingress and 1.96 s in proof execution/decode for the largest public PIE, within an 8.12 s command. The immutable 2.17 GB preprocessed artifact was validated, transposed in host memory, and uploaded during cold proofs. Nsight also showed 216 ms in mixed Blake2s leaf construction and over 450 ms in number-to-bit-reversed FFT kernels on that PIE.

The cumulative hypothesis: permute fixed columns on the GPU after vectorizable host validation; overlap captured-input hashing with parsing while retaining the independent path freshness hash; reuse a verified fixed device image within distinct multi-leaf batches; simplify FFT twiddle offsets and warp barriers; and compress complete non-final Blake2s blocks directly from registers. Predicted effects were a material cold-PIE command reduction, smaller proof-stage gains, unchanged single-PIE arena footprint, and a 2.17 GB capacity cost when the batch image is enabled. These changes compose in one patch.

## Changed source and mechanism

The patch applies to pinned stwo-zig commit b2873365dc28ed4bc4b27de10e01ea0beeef7c93 and includes the accepted frontier (challenge PR #6 and upstream stwo-zig PR #205). New work in this candidate:

- `src/backends/cuda/native/transform/lde.cu` and `src/backends/cuda/runtime/stages/transform.zig`: exact in-place SIMD-block permutation of a fixed column through a checked mode of the existing transform ABI. One writer owns each exchanged index pair.
- `src/integrations/cairo_cuda/executor/preprocessed_cache.zig`: full-column invalid-M31 flag in a vectorizable pass, followed by upload and GPU permutation for columns above log 16. SHA-256 still authenticates the original artifact bytes.
- `src/integrations/cairo_cuda/canonical_input.zig`: join an owned-byte hashing worker with parsing, retaining the independent second path hash after parsing.
- `src/products/cairo_cuda/app.zig`: default to the previously verified fixed device image for a distinct multi-leaf borrowed-runtime batch. `STWO_CAIRO_CUDA_STATIC_IMAGE=0` disables this capacity-for-latency choice.
- `src/backends/cuda/native/transform/n2b_fused.cuh` and `b2n_fused.cuh`: exact closed-form twiddle offsets replace per-thread loops; register-only warp shuffles no longer have a redundant preceding `__syncwarp`.
- `src/backends/cuda/native/commitment/progressive.cu`: load and compress complete non-final 16-word mixed leaves directly; keep the final block pending for Blake2s's final-block flag.

The cumulative patch also carries accepted-frontier source preparation, fixed-asset prefetch, batch ingress, and publication work under `src/integrations/cairo_cuda/canonical_source.zig`, `executor/ingress/controller_bundle.zig`, `src/products/cairo_cuda/ingress_jobs.zig`, `publication.zig`, and `src/products/circuit_recursion_cuda/main.zig`. No CPU, Metal, Rust, security, fixture, judge, or reference-output source is modified.

## Exploration and rejected variants

- A new exported CUDA transform symbol failed the kernel-closure gate. The accepted design uses a checked mode of the existing ABI and passes that gate.
- A 128-thread Cairo AIR launch showed no measurable proof-stage gain and was removed.
- Halving Cairo AIR code-generation slices from 16 to 8 roots passed exact proofs but raised the large-PIE proof stage from about 1.885 s to 1.931 s in an interleaved A/B/B/A check and raised sampled peak by 212 MB. It was reverted before capture.
- Source lookahead alone did not improve the integrated two-leaf command in a focused test and remains opt-in.
- The [bounded trace and lookup architecture](https://github.com/teddyjfpender/stwo-cuda-challenge/discussions/16) targets the main VRAM opportunity: trace evaluations, coefficients, and Merkle hashes remain live through AIR/OODS/opening. It requires exact replay or streaming across transcript barriers. This candidate does **not** claim that modeled memory saving or a 50% peak reduction.

## H200 public evidence

One exclusive H200 SXM, Zig 0.15.2 ReleaseFast, CUDA 12.8, sm_90. Each arm used a fresh process per case and a warmed fixture page cache. The direct qualifier timed adapted-input to published proof/process exit, sampled whole-device NVML peak, recorded reported ingress and proof-stage time separately, checked canonical proof/output/root digests, and invoked the pinned independent Rust Cairo verifier for standalone PIEs and registry leaves. Three interleaved full-basket passes per arm were ordered candidate/baseline/baseline/candidate/baseline/candidate. Times below are medians of three runs; device bytes are decimal GB. All ten candidate cases passed exact digest/output checks in all three passes.

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

## Proof checks, limits, and attribution

`python3 challenge.py check-data` passed all 10 cases/60 files. H200 `python3 challenge.py setup --build` passed and the active CUDA closure remained 147 symbols with 0 staged. `python3 challenge.py capture` validated derivative manifests and emitted the 52,609-byte cumulative patch; it applies to the original pin. `zig build test-cairo-cuda-local -Doptimize=ReleaseFast`, Zig formatting, and `git diff --check` passed. The required `python3 challenge.py benchmark --tier smoke --track balanced` was attempted, but the runner refused to start because this research pod has no pinned SHA-256 sandbox image. Direct qualification instead checked every public case three times. The direct qualifier does not invoke an independent circuit verifier; recursive proof bytes and canonical output/root/packed digests matched the pinned references exactly. Rust Cairo verification passed for the standalone and registry-leaf proofs.

Candidate binary SHA-256: Cairo `3d07ec77da720f7055ac78ede04087efe7799e292a09639dd86d1f6103f8ba38`, recursion `da6558cf2d23bbd14d53351fe9c2431ab34dab9d31eca96be47a2e83c0384229`. Saved accepted-frontier SHA-256: Cairo `64a3822be4c394662d7b916f1b0a249b4338b282c8716f6f55f94c8e9e8d360b`, recursion `39df63e951f5b31b5530afd4b5dbdcf6f134b30783bfdf78173dfdf5ef28649a`. Preparation/build time is excluded from command times.

The next substantial speed and capacity changes are bounded trace-evaluation/lookup materialization with exact decommit replay and independent sibling circuit folds on separate CUDA lanes after accounting for aggregate peak. They are tracked in [Discussion #16](https://github.com/teddyjfpender/stwo-cuda-challenge/discussions/16) and its [architecture follow-up](https://github.com/teddyjfpender/stwo-cuda-challenge/discussions/16#discussioncomment-18719294), not claimed as implemented here. Challenge [PR #11](https://github.com/teddyjfpender/stwo-cuda-challenge/pull/11) independently explores a fixed device image, and [PR #13](https://github.com/teddyjfpender/stwo-cuda-challenge/pull/13) independently explores vectorized M31 validation; their overlap is acknowledged.

Model/harness attribution: OpenAI Codex (GPT-6) through the Codex tool harness, directed by Theodore Pender. Public fixture, challenge, and source contributions are credited to their respective repositories. No private fixtures, proof blobs, logs, or binaries are included in the PR.

## Submission

The review PR containing this patch is the operator's review surface. The operator controls any `ready-to-judge` label; opening a PR does not itself create a ranked receipt.
