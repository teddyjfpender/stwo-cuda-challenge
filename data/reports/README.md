# H200 direct qualification, 2026-10-02

## Reviewed challenge PRs, 2026-10-02

The [review-status TSV](submission-review-2026-10-02.tsv) records the frozen
heads, patch and evidence digests, local validation, and disposition of PRs
[#3](https://github.com/teddyjfpender/stwo-cuda-challenge/pull/3),
[#4](https://github.com/teddyjfpender/stwo-cuda-challenge/pull/4), and
[#6](https://github.com/teddyjfpender/stwo-cuda-challenge/pull/6). The
[per-case research TSV](submission-research-2026-10-02.tsv) contains the ten
public cases measured for each of #4 and #6. No after-measurement exists for
#3. Its first reviewed head failed the pinned Zig 0.15.2 compile because it
passed a `usize` index to a `u32` parameter. The author pushed a corrected
`dbbf838` head; its exact recaptured patch now applies and passes the focused
Rust-checkpoint Cairo CUDA package tests (15/15). It is queued for H200 smoke
as submission `24e342a5d78c14b8973e`, with no speedup claimed yet.

PR #4's source is its immutable `36e8949` commit's
`candidate/MEASUREMENTS.json` (SHA-256 recorded on every row). Its 120 submitted
observations were checked for canonical-result flags, six samples per arm per
case, ABBA order, published medians, whole-device peak maxima, and paired
command ratios. These checks verify the **internal arithmetic and provenance of
the submitted data**, not the original GPU execution. The six PIE command
ratios are all slower (1.010–1.031), although the focused PoW primitive and
reported PoW device intervals are faster. The `median_paired_command_ratio`
column is the median of three ABBA round ratios and is **not** a ranked score.
The separate [PoW primitive TSV](submission-pow-primitives-2026-10-02.tsv)
recomputes all eight focused channel/bit-width ratios from 30 submitted
observations per arm. Its 26-bit ratios are 0.9304 (plain) and 0.9321 (M31)
for the synchronous circuit grind call, including allocation and transfer;
they are not full proofs and do not override the command regressions.

PR #6's source is its immutable `d2c8688` commit's `candidate/NOTES.md`
(digest recorded in the TSV). The table transcribes the author's one baseline
and one candidate direct H200 observation per case. Its command and ingress
times improved on all six PIEs; proof-execute/finish time was nearly unchanged.
The commands were not interleaved or isolated from builds, and the raw run
receipts were not attached. Its `median_paired_command_ratio` cells are blank;
the single-sample times are not paired evidence. PR #6 passed local pinned
source policy, apply, Cairo CUDA package tests (15/15), and the Cairo CUDA
product check. It was labeled `ready-to-judge`, frozen by manual intake as
submission `3f5cbe25c0c83453f5a8`, and prepared for a trusted build. This is
**queue admission**, not a ranked promotion or a claim that proof-stage time
improved.

All rows preserve the distinction between external whole-command time and the
Cairo backend's execute/finish diagnostic, which ends at `proof.finish` before
canonical verification and publication. Fold and pipeline proof-only times are
blank because a comparable trusted interval was not measured. Peak GiB values
are rounded; #4 uses the maximum of six independently sampled run peaks per arm,
and #6 uses the rounded values in its author's table. Neither direct run used the
qualified Docker judge, private holdout, three paired rank rounds, or a signed
receipt. They must not be combined with the older direct baseline as a score or
shown in the site's ranked leaderboard. PR #3 needs its first GPU measurement;
PR #4 needs a full-path winner; PR #6 awaits the trusted judge and proof-stage
epoch.

Two complete public-basket passes on one healthy NVIDIA H200 reproduced all
canonical proof and root hashes. Every Cairo proof passed its pinned Rust
verifier; every reported CUDA trial used the canonical 70-query, 26-bit PoW
profile with zero CPU fallbacks. The complete per-round measurements, binary
hashes, and PIE phase timings are in
[`h200-direct-2026-10-02.json`](h200-direct-2026-10-02.json). The
[`per-run TSV`](h200-direct-2026-10-02-runs.tsv) and
[`median TSV`](h200-direct-2026-10-02-summary.tsv) put measured proving phases
in their own columns; regenerate both with
`python3 scripts/export_h200_phases.py` from the repository root.
The pinned ReleaseFast baseline has a
[`build attestation`](h200-direct-2026-10-02-baseline-attestation.json), and a
separate clean zero-patch candidate worktree has its own
[`build attestation`](h200-direct-2026-10-02-candidate-empty-attestation.json).
Both worktrees were at the pinned source commit. The direct proof runs used the
baseline binaries; the candidate build has not been scored in a paired A/B run.

## Historical research context

The [Cairo CUDA milestone TSV](historical-cairo-cuda-milestones.tsv) adds 48
version-by-PIE rows from the verifier-qualified `stwo-zig/autoresearch` H200
receipts. It follows the **same four historical SN PIE inputs** through v39,
v41, v42, v44, v45, and retained Hopper v5–v9, v17, and v18 milestones. These
four inputs are different from the six public cases below. Each row now carries
the source PIE's OS steps, archive size, component count, padded component rows,
and EC/Pedersen/Poseidon/bitwise/range-check builtin counts from the pinned
source-coverage record. Each row also gives the backend-reported proof-stage
median, separate ingress/publication/process
timings, sample count, maximum sampled device memory, input/proof/binary hashes,
and the source receipt's relative path and SHA-256. All imported proofs passed
the official Rust verifier at the canonical 70/26/24 profile with zero CPU
fallback. Failed proofs and rejected variants are excluded.

| Historical cold proof stage | SN PIE 1 | SN PIE 2 | SN PIE 3 | SN PIE 4 |
| --- | ---: | ---: | ---: | ---: |
| v39, one accepted run each | 3.784 s | 2.955 s | 3.772 s | 3.170 s |
| v45, three-run medians | 2.218 s | 1.504 s | 2.206 s | 1.595 s |
| Hopper v5, two paired-run medians | 1.889 s | 1.323 s | 1.878 s | 1.492 s |
| Hopper v8, two paired-run medians | 1.193 s | 0.811 s | 1.190 s | 0.944 s |
| Hopper v18, one accepted run each | 1.034 s | 0.657 s | 1.030 s | 0.798 s |

This is a trajectory across versions and H200 sessions, **not** one paired
v39-versus-v18 trial or a score against the challenge basket. The source
receipts use the historical `proof_execute_and_decode_ns` backend counter;
they exclude ingress, publication, external Rust verification, PIE execution,
adaptation, and queueing. The TSV preserves those other available clocks in
separate columns. The paired v5–v8 rows select the candidate arm and exclude
the explicitly disqualified v5 timing block.

The [workload-shape TSV](pie-workload-shapes.tsv) places those four historical
PIEs beside the six public PIEs using a **step index**: each step count divided
by the historical four-PIE median of 14,066,633 steps. The public cases have
18.8–33.7 million steps, or 1.34–2.39 times that reference. Their median is
about 1.60 times the historical median. The public table also records block
count and CPI bytes. Archive bytes for the historical inputs and CPI bytes for
the public inputs are separate columns because those formats have different
overheads. For the public CPI files, the exporter reads and hash-checks the
pinned transport header and reports opcode, memory-table, and **reserved
builtin segment capacity** counts. These are exact input geometry, but reserved
capacity is not the number of builtin operations actually executed. The
historical record supplies executed builtin counts, so the table keeps those
two kinds of counts in separate columns. The public fixture also labels each
case's notable builtin mix. The step index models **workload size only**.
Ten heterogeneous inputs, with public executed builtin and component counts
unavailable, cannot
support a defensible cross-cohort proof-time or memory prediction. No historic
timing is rescaled into a public-case benchmark.

The public four-block case has 33.7 million steps, 36.9 million memory
addresses, and 134.1 GB measured peak H200 memory; it is the largest public
input on all three measures. The one-block cases span 18.8–25.4 million steps
and 21.1–27.9 million memory addresses. Their measured peaks still range from
84.6 to 116.3 GB, showing why step count alone is insufficient as a memory
model. These are descriptive measurements of the fixed basket, not predictions
for unseen PIEs.

Regenerate the historical TSV from a clean `stwo-zig` checkout containing the
cited receipts with `python3 scripts/import_autoresearch_history.py --source
workspace/stwo-zig`, then run `python3 scripts/export_pie_workload_shapes.py`.
The importer checks security, independent verification, stable input and proof
digests across revisions, source PIE hashes, and sample counts. It writes only
repository-relative source paths; no machine-local paths from old driver logs
are copied.

## Current H200 public basket

| Public case | Measured proving phase | Ingress | Whole command | Peak H200 memory |
| --- | ---: | ---: | ---: | ---: |
| PIE `15582797_15582797` | 1.28 s | 5.80 s | 7.63 s | 90.5 GB |
| PIE `15603744_15603744` | 1.22 s | 5.76 s | 7.50 s | 89.7 GB |
| PIE `15581148_15581148` | 1.17 s | 5.23 s | 6.90 s | 84.6 GB |
| PIE `15590913_15590913` | 1.55 s | 5.67 s | 7.78 s | 105.2 GB |
| PIE `15588777_15588780` | 1.95 s | 7.19 s | 9.78 s | 134.1 GB |
| PIE `15591789_15591789` | 1.68 s | 6.30 s | 8.58 s | 116.3 GB |
| Two-leaf recursive fold | unavailable | — | 2.90 s | 29.4 GB |
| Eight-distinct-PIE recursive fold | unavailable | — | 7.90 s | 29.4 GB |
| Two-leaf serial PIE-to-root pipeline | incomplete: Cairo leaves 0.93 s | — | 18.44 s | 69.5 GB |
| Two-leaf integrated-batch PIE-to-root pipeline | incomplete: Cairo leaves 0.77 s | — | 14.04 s | 41.3 GB |

The PIE proving phase is the backend's `proof_execute_and_decode_ns` counter,
converted to seconds. Despite that historical name, the timer ends at
`proof.finish`, **before** canonical verification, decoding, and publication;
it covers CUDA proof execution and finishing, not the entire command. Fold
`fold_stage_s` is 2.35 s for two leaves and 7.35 s for eight leaves, but it
also includes host construction and runtime lifecycle, so it is **not** a
proof-only value. The pipeline receipt contains Cairo leaf proof phases but
omits resident wrap/fold proof durations. The TSV leaves `proof_stage_s` empty
for both recursion and pipeline cases rather than substituting their whole
command time. Future H200 runs must retain each circuit `resident_ns` counter
and a trusted proof-stage interval before a complete proof-only comparison can
be ranked.

Whole-command time remains useful for measuring cold start, ingestion, and
publication overhead; it is the separate H200 v1 challenge metric. If the
production service supplies prepared GPU inputs, it should optimize and rank
an explicitly new proof-stage contract, while still reporting whole-command
time as an operational diagnostic. These two timing scopes must not be mixed
in a score or a historical comparison. Independent verification runs after
measurement. The standalone PIE Rust verifier took 0.051–0.069 seconds per
proof and is recorded separately. Peak memory is whole-device NVML usage
sampled every 10 ms. The
H200 reports 150.75 GB total device memory, so the largest public PIE stayed
below both capacity and the contract's 6 GB reserve. The two complete passes
took 90.1 and 92.8 seconds respectively, including command startup and
publication. For PIEs, ingress takes 5.2–7.2 seconds, versus 1.2–2.0 seconds
for proof execution and finishing. The staged static assets and source compilation
are the largest ingress components; their exact times are retained per case.

These runs were **direct, unranked, and unsandboxed**. They establish H200
functionality and reference equivalence, not a leaderboard score. Docker and
mounted output-quota isolation were not qualified on this Runpod pod; private
holdout, signed receipt, and paired A/B ranking remain activation
gates in [`spec/ACTIVATION.md`](../../spec/ACTIVATION.md). The first rented
Community Cloud H200 was discarded after a minimal CUDA context test returned
error 46 and NVML reported a GPU reset recovery action. No proof timings from
that faulty host are included here. The qualifying Secure Cloud H200 used
driver 580.178.04 and the pinned source commit recorded in the JSON report.
