# Proof-v2 scoring contract

The [proof-v2 contract](../benchmark-proof-v2.json) fixes six Cairo PIEs, two
recursive folds, and one integrated two-PIE-to-root pipeline. Every backend
uses the same [hash-pinned inputs](../fixtures/public-proof-v2.json) and exact
expected proof or root bytes. A submission chooses one backend: CUDA H200,
Metal M5 Max, or CPU M5 Max. These are separate rankings, not cross-device
speed comparisons.

Only prover-call intervals count. A standalone PIE has one Cairo stage; a
fold with `n` leaves has `n - 1` fold stages; the two-leaf pipeline has two
Cairo, two wrap, and one fold stage. Input loading, fixed-data preparation,
compilation, serialization, publication, independent verification, and
whole-command time are diagnostics. Memory is a host-capacity gate, not a
score multiplier. All security parameters and output hashes remain fixed.

For each case, take the median of paired candidate/baseline proof-time ratios
on the same backend and host. Each of the PIE, recursion, and pipeline
families receives one third of the total log weight, divided equally among
its cases. If `r_i` is a case ratio and `w_i` its weight, the speed score is
`exp(-sum_i w_i * ln(r_i))`; baseline is 1 and higher is faster. The
[scorer](../harness/proof_score.py) requires at least three paired rounds,
complete stage counts, exact verification and input checks, timer/source
binding, memory admission, and A/A noise calibration for a ranked promotion.

The epoch is [staging](ACTIVATION.md). Direct `benchmark-proof` and
`compare-proof` runs help research but cannot publish a rank. The former
H200 command-time and memory-weighted scoring is [archived](LEGACY_SCORING.md)
and its Actions workflow is disabled.
