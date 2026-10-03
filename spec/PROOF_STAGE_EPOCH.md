# Next epoch: proof execution on CUDA, Metal, and CPU

The next challenge scores **proof execution time only**. CUDA runs on one
exclusive H200; Metal and CPU run independently on this 64 GB M5 Max. Each
backend receives the **same nine unique proof jobs, hash-pinned CPI/leaf
inputs, ordered tree, registry, and canonical security profile** in
`fixtures/public-proof-v2.json`. The v1 serial and resident-batch pipeline
cases used the same inputs and circuit proofs; after loading and process reuse
leave the score, they are one job rather than duplicate evidence.
Each has its own baseline and latency leaderboard. Cross-backend absolute
times may be compared as observations, but a candidate is scored only against
the pinned baseline of its selected backend on the same host. Device/host
memory remains a capacity and correctness gate, never a score multiplier.

For a standalone Cairo case, `proof_time_s` covers input-dependent witness
generation, commitments, composition, FRI, PoW, and proof finishing. It excludes
CPI file loading, parsing, geometry compilation, fixed-asset initialization,
proof encoding/publication, candidate-side verification, and the independent
judge verifier. The current CUDA `proof_execute_and_decode_ns` and shared
CPU/Metal `timing.prove_ns` are **diagnostic examples of this boundary**;
their backend receipts alone are not trusted rank timers.

For a fold case, the metric is the sum of one circuit-proof execution interval
per reduction: one for two leaves, seven for eight. It excludes reading leaf
files, multiverifier construction, canonical preprocessing, host conversion,
verification, and output publication. For a PIE-to-root pipeline, sum all Cairo
leaf proof intervals, one wrap proof per leaf, and one fold proof per reduction.
No proof may be omitted,
cached from an earlier request, or shifted outside the recorded proof intervals.
The judge verifies the final Cairo and root proof bytes and ordered statements
after timing. The elapsed whole command and preparation stages remain optional
operational diagnostics; they do not enter score files or promotion decisions.

The timer must be fixed by the trusted judge or a hash-checked, uneditable
instrumentation layer in the pinned prover. The candidate must not be able to
move input-dependent work before the measured interval or forge, truncate, or
rename the intervals. Public and private inputs are withheld until the frozen
measurement boundary. A deliberately dishonest candidate that reports a tiny
internal timer must not improve the score. CUDA's current product-level timer
and circuit `resident_ns` are emitted from editable source, so the implemented
`h200-v1` judge cannot be relabeled or ranked as proof-only. CPU/Metal Cairo's
shared timer is outside the current editable surface, but the complete fold
and pipeline timer set still needs an authenticated interface.

The new scorer keeps equal log-weight for the `pie`, `recursion`, and `pipeline`
families, split equally within each family. For backend `b`, with paired
candidate/baseline proof-time ratios `r_i`, its only ranked score is
`exp(-Σ_i w_i log r_i)`. Run at least three idle-host ABBA rounds, a baseline
A/A calibration, and the existing bootstrap promotion gate **per backend**.
CUDA retains whole-device memory sampling and a 6 GB reserve as an admission
gate. M5 CPU and Metal use whole-process/whole-system memory checks against a
host-specific reserve; Metal's unified memory must not be presented as
independent VRAM. Memory metrics, cold command time, ingress, and publication
are recorded but never used as a score denominator or tie-breaker.

Activation requires a frozen all-nine-case adapter on each backend, exact
security and independent verifier acceptance, complete Cairo/wrap/fold stage
counts, trustworthy timer tests, source/build attestation, private holdouts,
memory admission, and fresh backend-specific baselines. The M5 64 GB host must
prove every selected public and holdout case before its CPU or Metal ranking
opens. macOS physical footprint can exceed installed RAM when compression and
swap are used; M5 admission must consider memory pressure, swap/disk headroom,
and successful completion rather than reject on that counter alone. A case
that exceeds capacity is a failed qualification, not an excuse
to replace it with a smaller job while claiming the same basket. Until those
gates pass, the website must label old H200 command data as historical and
new proof-stage measurements as unranked research.

## Local qualification evidence and source transition

The [M5 smoke record](../data/reports/m5-proof-smoke-2026-10-03/README.md)
checks four unique public jobs on both CPU and Metal. Exact Cairo and
recursive proof bytes matched the pinned references. The successful standalone
PIE already used 52–53 GB peak physical footprint. The serial pipeline worked only after the
one-line compact-CPI reader fix from upstream `stwo-zig@0301ccfdb`; the
current pinned `b2873365` checkout still has the JSON-only reader. A new
epoch must pin an upstream source containing this fix (and rebase or retire
the accepted CUDA frontier, which upstream PR #206 has already absorbed),
then collect fresh baselines under that exact pin. Historical H200 command
measurements cannot serve as proof-only score denominators.

Three [capacity probes on the newer source pin](../data/reports/m5-main-capacity-2026-10-03/README.md)
then proved the 25.38M-step EC outlier and 33.68M-step four-block PIE exactly
on CPU, and the largest PIE exactly on Metal. Compact polynomial storage and
four workers let the largest case finish on both backends: 203.52 s CPU and
216.30 s Metal proof stage, with 77.98 GB and 76.84 GB reported peak physical
footprints respectively. The other public cases and private holdouts remain
unqualified on the proposed pin.

The staged [`benchmark-proof-v2.json`](../benchmark-proof-v2.json) pins upstream
`97510e52`, after the accepted PR #17 improvements were upstreamed. Its
candidate edit surfaces exclude the timer-owning product files; timer-file
digests are fixed separately per backend. The staged proof scorer validates
one Cairo proof per standalone PIE, one proof per fold reduction, and two
Cairo plus two wrap plus one fold proof for the remaining pipeline job. It
scores only those stage intervals, with memory as an admission gate. This is
staging code: the current `benchmark.json` remains the h200-v1 command-time
contract until new timer receipts, judge runners, and complete backend
baselines qualify.
