# Direct qualification reports

## Metal PR #22 research promotion, 2026-10-04

The [nine-case comparison TSV](m5-metal-pr22-2026-10-04.tsv) transcribes the
M5 Max proof-stage and command times from the merged [submission PR #22](https://github.com/teddyjfpender/stwo-cuda-challenge/pull/22)
and joins each row to the full-precision published Metal baseline below. The
submitted patch applies to the pinned source and changes only allowed Metal
paths. No benchmark or independent verifier was rerun for this promotion, at
the submitter's request. Candidate timings and exact-output results are
**author-reported, direct, unpaired, and unranked**. The table uses one run
per arm; it is not a confidence interval or a signed scorecard.

The reported family-weighted proof-time comparison is **1.5217×**: two-leaf
fold 10.412 → 4.181 s, eight-leaf fold 73.565 → 29.310 s, and two-leaf
pipeline 71.350 → 55.653 s. The six Cairo PIEs show a geometric-mean 9.0%
reduction; the four-block and near-capacity PIEs were nearly flat. Focused
wrap and fold checks in the PR notes report about 13.8% lower process RSS,
while the largest PIE's physical footprint was unchanged. The accepted patch
is [the Metal frontier](../../frontier/proof-v2/metal/manifest.json) for new
participant work, without changing the pinned clean baseline or activating a
ranked result.

## RISC-V CSP M5 Max baseline, 2026-10-04

[`m5-csp-v1-2026-10-04.tsv`](m5-csp-v1-2026-10-04.tsv) records the first
complete RISC-V CSP suite on the pinned `stwo-zig` source
(`068b467b71e0b35533409c63a5cc509aefdc9736`) for both lanes of
[`benchmark-riscv-csp-v1.json`](../../benchmark-riscv-csp-v1.json): all 16
cases on CPU and on Metal, Apple M5 Max 64 GB, on AC power.
`proof_duration_s` is the CSP report's `proof_duration` (guest execution,
witness construction and proof generation); verification, execution, witness
and proving phases are listed separately. CPU proof durations are
0.48–1.64 s and Metal 0.47–1.59 s per case.

Every proof verified, every output matched its pinned digest, and the
invalid-signature fixture was proved and rejected on both backends. Each
case is a **single sample with no warm-up**, so this is a direct, unranked
starting baseline, not a paired score. The Metal report flags that not every
resident-polynomial dispatch was verified
(`metal_resident_dispatches_verified=false`), and both reports are
`host-qualified-non-comparable`: the M5 Max is not the EthProofs M1
publication host. `report_sha256` binds each row to its local harness report.

## Proof-v2 H200 public basket, 2026-10-03

The [nine-row observation TSV](h200-proof-v2-2026-10-03-full.tsv) and
[raw direct receipts](h200-proof-v2-2026-10-03-direct.json) record one complete
CUDA pass over the **same nine public jobs** used by CPU and Metal below. The
H200 used clean `stwo-zig@1433d61b`, ReleaseFast SM90 binaries, canonical
security, and the protected proof-call timers from upstream PR #213. The
[prepare](h200-proof-v2-2026-10-03-preflight.json) and
[direct](h200-proof-v2-2026-10-03-direct-preflight.json) preflights checked the
source pin, fixture hashes, CUDA artifacts, and idle device. The TSV records
measured peak **device** bytes in its footprint column; the raw receipts retain
the stage breakdown, command time, binary/timer hashes, and verifier results.

| Job | Proof s | Whole command s | Peak device GB |
| --- | ---: | ---: | ---: |
| PIE 15582797 | 1.246 | 5.681 | 90.47 |
| PIE 15603744 | 1.192 | 5.387 | 89.70 |
| PIE 15581148 | 1.139 | 5.326 | 84.53 |
| PIE 15590913 | 1.503 | 5.782 | 105.20 |
| PIE 15588777–15588780 | 1.879 | 6.780 | 134.06 |
| PIE 15591789 | 1.630 | 5.824 | 116.24 |
| Two-leaf fold | 0.555 | 2.579 | 29.41 |
| Eight-distinct-leaf fold | 2.794 | 7.280 | 29.41 |
| Two-leaf PIE → wrap → fold root | 2.669 | 15.252 | 69.43 |

The integrated pipeline proof interval is two Cairo proves (0.441 and
0.434 s), two wraps (0.639 and 0.591 s), and one fold (0.565 s). All nine
published proof/root hashes matched the pinned references. The six standalone
PIE proofs passed the official Rust Cairo verifier. The pipeline verified its
Cairo leaves in process and kept them resident; it did not serialize leaf
proofs for the Rust verifier. The direct qualifier did not run an independent
circuit-root verifier. These measurements are **unranked, unsandboxed, and
single-pass**; they do not establish paired speedups or variance. A local
runtime-artifact bundle and its digest manifest were retained before stopping
the paid H200 pod; see [the artifact receipt](h200-proof-v2-2026-10-03-artifacts.json).

## Proof-v2 M5 Max public basket, 2026-10-03

The [full observation TSV](m5-proof-v2-2026-10-03-full.tsv) contains one exact,
unranked pass of all nine proof-v2 public jobs on each M5 Max backend, CPU and
Metal. Both runs used the clean pinned `stwo-zig@1433d61b` source, the same
hash-checked inputs, and the protected proof-call timers from merged upstream
PR #213. Every Cairo proof and recursive root matched its pinned output hash.
The exporter rehashed the actual artifacts and receipts before publication.
There were no candidate edits or paired trials, so these are diagnostic
observations and **not** ranking baselines. Earlier two-leaf smoke receipts
remain in [the separate summary](m5-proof-v2-2026-10-03-summary.tsv).

| Job | CPU proof s | Metal proof s | CPU command s | Metal command s |
| --- | ---: | ---: | ---: | ---: |
| PIE 15582797 | 41.083 | 42.544 | 42.415 | 43.941 |
| PIE 15603744 | 42.175 | 41.533 | 42.903 | 41.905 |
| PIE 15581148 | 39.700 | 38.209 | 40.385 | 38.864 |
| PIE 15590913 | 93.480 | 137.763 | 93.891 | 138.232 |
| PIE 15588777–15588780 | 206.007 | 245.816 | 206.757 | 246.684 |
| PIE 15591789 | 99.243 | 155.392 | 99.970 | 155.951 |
| Two-leaf fold | 6.203 | 10.412 | 8.587 | 12.611 |
| Eight-distinct-leaf fold | 46.105 | 73.565 | 50.957 | 78.564 |
| Two-leaf PIE → wrap → fold root | 100.138 | 71.350 | 105.969 | 77.286 |

PIE rows include the process's peak physical footprint in the TSV, roughly
44–78 GB on CPU and 44–77 GB on Metal; recursive rows do not have a comparable
peak measurement. The pipeline proof interval sums two Cairo proves, two
wraps, and one fold. The command column includes all leaf commands and the
fold command. These backends shared one host and were run sequentially, but
one pass does not establish comparative throughput or variance. The H200
result above uses the same public proof-v2 jobs and source pin.

## H200 direct qualification

## Upstream CUDA ingress PR #212, 2026-10-03

Merged upstream [PR #212](https://github.com/teddyjfpender/stwo-zig/pull/212)
authenticated the owned CPI capture, delayed one-request source lookahead until
after fixed-data admission, and corrected arena admission to include reusable
pages retained by CUDA's private async pool. The
[per-leaf TSV](h200-pr212-ingress-2026-10-03-runs.tsv) has 24 rows across
two- and four-distinct-PIE ABBA sequences; the
[summary TSV](h200-pr212-ingress-2026-10-03-summary.tsv) has the four cohort/arm
means. Both preserve the exact source and binary hashes, CPI identity and size,
whole-command and per-leaf ingress/proof timings, 10 ms sampled whole-device
peak, proof hash, and the SHA-256 and line of their original raw receipt in the
[proving-service evidence](https://github.com/teddyjfpender/proving-service/tree/3e8cd9d/data/h200-ingress-212).
These TSVs are copied from those saved H200 receipts; no new GPU run or
revalidation was performed for this challenge-repository import.

| Distinct PIEs | Baseline + pool fix, mean command | PR #212, mean command | Baseline / candidate mean ingress sum | Device peak |
| --- | ---: | ---: | ---: | ---: |
| 2 (377/102 MiB) | 11.325 s | 10.458 s | 5.077 / 4.204 s | 97.22 GB |
| 4 (377/408/102/663 MiB) | 22.820 s | 19.143 s | 10.738 / 6.859 s | 142.65 GB |

The command reductions are 7.7% and 16.1%; summed ingress reductions are
17.2% and 36.1%. All four leaf proof hashes matched between arms in every
four-PIE run. The comparison baseline was upstream main `744664585` plus only
the common pool fix; its receipt's `source_commit` is the underlying main
commit, and the TSV records that overlay explicitly. The optimized binary was
built from `ab56a3ff2` and has SHA-256
`c3d124faa0ce39fd6255da79d8310ba27721e941b6b9b68a406030072921c69b`.
The 663 MiB leaf needs the pool fix even in an otherwise baseline build to
finish its circuit wrap. These are fresh-process, direct, unranked diagnostics
of the circuit leaf lane, **not** the fixed ten-case challenge basket or a
90% warm-service ingress result. They do not update `benchmark.json`, the
accepted participant frontier, the website leaderboard, or score denominators.

## Challenge PR #17, 2026-10-03

[PR #17](https://github.com/teddyjfpender/stwo-cuda-challenge/pull/17) was
independently built from its cumulative 65,253-byte patch and measured on one
H200 against the frozen source pin. The [raw direct runs](h200-pr17-direct-2026-10-03-runs.jsonl),
[experiment identity](h200-pr17-direct-2026-10-03-experiment.json),
[preflight](h200-pr17-direct-2026-10-03-preflight.json), and
[smoke gate](h200-pr17-direct-2026-10-03-gate.json) retain three interleaved
full-basket passes per arm, plus repeated PIE/fold smoke. All 60 full proof
commands matched the exact canonical proof or root/output digests; the pinned
Rust Cairo verifiers accepted every applicable PIE and pipeline leaf. No CUDA
trial fell back to CPU. The direct qualifier does not run an independent
circuit verifier, but recursive bytes matched the pinned references. These are
unranked, unsandboxed research results, not judge receipts.

The median paired external-command ratio is 0.716 for six PIEs, 0.928 for two
folds, and 0.826 for two pipelines. With equal family weights, the research
basket ratio is 0.819 (1.22× inverse-latency gain) relative to the frozen pin.
The large PIE's median command fell from 12.509 to 9.246 s and its ingress
from 9.389 to 5.981 s. The eight-leaf fold fell from 10.802 to 9.447 s, with
circuit-resident proof time from 4.265 to 3.146 s. Whole-device sampled peak
was unchanged on nine cases; the integrated batch rose from 38.445 to 40.445
GiB because its fixed device image retains about 2 GiB. All per-case command,
proof-stage, ingress, and memory medians are in the
[research TSV](submission-research-2026-10-03.tsv), selected for the website
by [`data/site/sources.json`](../site/sources.json).

A separate [accepted-frontier comparison](h200-pr17-frontier-2026-10-03-runs.jsonl)
on the same H200 used four interleaved observations per arm of the large PIE
and eight-leaf fold. Its [gate](h200-pr17-frontier-2026-10-03-gate.json)
records 18.4% lower PIE command time, 11.6% lower fold command time, and 27.7%
lower fold circuit-resident time. The incremental comparison is not mixed
into the website's frozen-pin improvement trajectory. Absolute command times
on this pod are higher than the PR author's pod; paired same-host ratios are
the relevant comparison. The author also reports a smaller integrated-batch
command regression relative to the intermediate PR #17 version; the
independent pin-relative pass here still shows a large cumulative gain.

Before the H200 pod was shut down, its PR #17 Linux prover binaries, generated
CUDA AOT packs and native archives, canonical fixed assets, required Cairo and
circuit vectors, pinned Rust verifiers, CUDA runtime library, and exact source
patch were copied to the **local, Git-ignored**
`.cache/pr17-service-h200-sm90/` bundle. Its `README.md` gives the runtime
environment and its `MANIFEST.json` hashes all 566 files. The committed
[artifact record](h200-pr17-service-artifacts-2026-10-03.json) binds the bundle
manifest and principal binaries/assets to the reviewed PR and direct evidence.
This bundle is for an H200-class Linux service; it is not a macOS executable
or a ranked submission artifact.

## Reviewed challenge PRs, 2026-10-02

The [review-status TSV](submission-review-2026-10-02.tsv) records the frozen
heads, patch and evidence digests, local validation, and disposition of PRs
[#3](https://github.com/teddyjfpender/stwo-cuda-challenge/pull/3),
[#4](https://github.com/teddyjfpender/stwo-cuda-challenge/pull/4), and
[#6](https://github.com/teddyjfpender/stwo-cuda-challenge/pull/6). The
[per-case research TSV](submission-research-2026-10-02.tsv) retains #4's
author-reported ten-case research and summarizes new independent H200 evidence
for #3 and #6. The [per-run H200 TSV](submission-h200-runs-2026-10-02.tsv)
contains all 148 independently collected observations: #3 has two samples
per arm on each of six PIEs and one per arm on two pipelines; #6 has three
ABBA rounds and six samples per arm on all ten public cases. Each row records
the measured command, available phases, 10 ms sampled whole-device peak, and
actual proof hash. The reviewed heads and patch hashes in the review TSV bind
these observations to the exact submitted sources. All these H200 proofs and
roots matched the pinned canonical outputs, the Cairo proofs passed the
independent Rust verifiers, and no CUDA trial fell back to CPU.

PR #3's first head failed the pinned Zig 0.15.2 compile because it passed a
`usize` index to a `u32` parameter. The author corrected it at `dbbf838`;
that head passes the focused Rust-checkpoint Cairo CUDA tests (15/15).
Independent H200 PIE ratios are mixed, from 0.930 to 1.051, and both pipeline
commands are slightly slower. Its predicted large gain is not supported, so
the PR remains research-only.

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

PR #6's immutable `d2c8688` patch was independently built and measured in
three idle-host ABBA rounds. The six PIEs each improve by roughly 16–23% in
whole-command time, with proof-execute/finish nearly unchanged. The gain is in
ingress, especially fixed-asset loading overlapped with source work. Device
peaks are essentially unchanged. The two fold cases are near baseline; the
serial pipeline is near baseline and the integrated pipeline is slower.
The three-family geometric time ratio is 0.930 (7.5% inverse-latency gain).
The same runs' baseline A/A median absolute log dispersion implies an 11.3%
noise threshold, above that aggregate gain. The operator promoted it as
**independently validated direct H200 research**, separate from ranked scores.

All rows distinguish external whole-command time from the Cairo backend's
execute/finish diagnostic, which ends at `proof.finish` before independent
verification and publication. Fold and pipeline proof-only cells are blank
because no comparable trusted interval was measured. Peak GiB is the maximum
sampled whole-device usage per arm, rounded for display. #4's observations
remain author-reported; #3 and #6 are independent direct diagnostics. The
restricted Runpod H200 does not have the Docker judge or output-image mount
capability, so none of these observations has private holdout isolation or a
signed rank receipt. They are not leaderboard scores, and command-time gains
must not be presented as proof-stage gains. #4 still needs a full-path winner;
#6 needs a qualified judge and enough aggregate gain to clear variance.

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

The [main research TSV](submission-research-2026-10-03.tsv) also carries the
historical trajectory **under the same six current public PIE case IDs** as
the challenge baseline and PR measurements. `record_kind` distinguishes
`historical_model`, `challenge_baseline`, and `submission` rows. The older
four-PIE measurements remain in the provenance TSV above; they do not appear
as separate challenge cases. For each historical milestone, the generator
takes the geometric mean of its four source-PIE proof-time ratios against
Hopper v18 and applies that factor to each current public PIE's measured
baseline proof stage. Every historical row is therefore an **estimate for a
different input**, not a measured proof or ranked result. `estimate_low_s` and
`estimate_high_s` express uncertainty from the four source ratios.

The v37 receipt has three verified source proofs; its first PIE failed. The
v33/v35 source values and missing v37 value are separately backcast with a
log-linear fit to the earliest verified receipts and a Student-t prediction
interval. Those intervals are propagated to the six current cases. Early
revision labels describe a statistical reconstruction, not a claim that a
passing proof existed then. Each model row retains the source receipt paths,
SHA-256 digests, method, and zero measured samples. Regenerate the blended TSV
from the pinned receipts with
`python3 scripts/blend_proof_history.py --source /path/to/stwo-zig`.

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
