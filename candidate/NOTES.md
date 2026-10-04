# Metal proof-v2 candidate: circuit evaluation retention and BLAKE2s streaming

**Backend:** Metal on the 64 GB Apple M5 Max. **Source pin:** `stwo-zig@1433d61b590058980d02b3f5bc912fe073c1a646`. **Patch:** `candidate/proof-v2-changes.patch`. This is a staged, unranked proof-only research submission; the paired judge and private holdouts are not active.

## Bottleneck and mechanism

The circuit Metal wrapper inherited compact coefficient storage from the CPU integration even at FRI blowup one. Wraps and folds then re-extended those coefficients for later proof consumers. The Metal wrapper now retains committed evaluations when blowup is one, leaving other circuit configurations on the caller's policy. A focused wrap A/B produced identical proof bytes while cutting its wrap interval from 10.035 s to 4.411 s and peak process RSS from 17.071 GB to 14.713 GB.

The compact BLAKE2s leaf stream also copied carried columns into Metal a second time and created multiple Metal buffer views for columns in the same backing. Carried columns now use page-aligned owners that Metal can alias, and one view is reused per backing in a block. Consecutive blocks at the same row height update independent per-row hash states in place, avoiding a second leaf-state buffer. This preserves the leaf order, hash function, roots, and proof bytes.

Changed source paths, all within the allowed Metal surface:

- `src/integrations/circuit_metal/mod.zig` — evaluation retention for blowup-one circuit proofs.
- `src/backends/metal/runtime/compact_streaming_committer.zig` — page-aligned carried-column ownership.
- `src/backends/metal/runtime/blake2_leaf_stream.m` — backing-view reuse and same-height in-place state.
- `src/backends/metal/tests/leaf_stream.zig` — exact roots/layers and alias tests.

## Public exact-output evidence

Each row is **one direct observation per arm**, on the same source pin and M5 host. Baseline comes from `data/reports/m5-proof-v2-2026-10-03-full.tsv`; candidate comes from a complete `benchmark-proof --backend metal` run. Times are seconds. The first pair is proof-call stage time; the second is whole-command time, which is diagnostic only. Every candidate proof/root matched the pinned reference hash.

| Public case | Proof baseline → candidate | Command baseline → candidate | Exact |
| --- | ---: | ---: | :---: |
| PIE 15582797 | 42.544 → 35.855 | 43.941 → 36.653 | yes |
| PIE 15603744 | 41.533 → 35.384 | 41.905 → 36.142 | yes |
| PIE 15581148 | 38.209 → 33.036 | 38.864 → 33.625 | yes |
| PIE 15590913 | 137.763 → 137.467 | 138.232 → 137.883 | yes |
| PIE 15588777–15588780 | 245.816 → 226.890 | 246.684 → 227.597 | yes |
| PIE 15591789 | 155.392 → 153.974 | 155.951 → 154.720 | yes |
| Two-leaf fold | 10.412 → 4.181 | 12.611 → 6.625 | yes |
| Eight-leaf fold, seven reductions | 73.565 → 29.310 | 78.564 → 34.123 | yes |
| Two-leaf Cairo/wrap/fold pipeline | 71.350 → 55.653 | 77.286 → 62.111 | yes |

The direct comparison tool reports a **1.5217× score-like proof-time speedup**, equivalent to about 34.3% less family-weighted proof time: PIE family 9.0% less, recursion 60.0% less, pipeline 22.0% less. It is an **unranked, unpaired research comparison**, not a leaderboard result or a confidence interval. The final pipeline's two wrap calls were 4.598 s and 4.632 s, versus 10.109 s and 10.254 s before enabling evaluation retention for wraps; the fold call remained 4.480 s.

## Memory, checks, and limits

- A focused `/usr/bin/time -l` run on the same public wrap input measured maximum process resident set size at **17.071 → 14.713 GB** (−13.8%) for compact versus evaluation-only Metal storage. The wrap proof interval was **10.035 → 4.411 s** (−56.0%). Both wrapped output SHA-256 values were identical.
- A two-leaf fold direct command measured maximum process RSS at **16.904 → 14.579 GB** (−13.8%) for pristine baseline versus the composed candidate. Both proof, public-output, and packed-root hashes matched the pinned reference. These RSS figures are process memory, not separate VRAM on unified-memory Apple silicon.
- The runner's PIE peak *physical footprint* is essentially unchanged on the largest cases: for PIE 15588777–15588780 it was **76.840 → 76.841 GB**. That counter can exceed installed RAM under compression/swap; the case completed exactly. This candidate does not claim a large PIE memory reduction.
- `setup-proof --backend metal --build` built Cairo and recursion products. `zig build test-native-metal -Doptimize=ReleaseFast -j2` passed its native Metal tests, lifecycle proof, and independent native-example verification. `harness/check_contract.py --config benchmark-proof-v2.json` passed; `git apply --check` confirmed the captured patch applies to the pinned baseline.
- The complete final basket passed all nine pinned proof/root hashes, including the Cairo product's `--verify` checks and the pipeline's two Cairo, two wrap, and one fold timer intervals. No security parameters, fixtures, product timer files, judge code, or reference outputs changed.

The four-block and 15591789 PIEs were nearly flat, and whole-PIE peak footprint did not materially improve. Earlier alternatives were rejected after focused tests: a larger composition tile reduced submissions but raised memory and slowed the small PIE; larger commit arenas increased peak; radix changes and retaining extra Merkle layers did not help. Faster noncompact Cairo storage modes raised peak memory and were not adopted because the direct runner fixes compact polynomial storage for capacity. The host/GPU trace also showed substantial CPU witness and data-movement time, so this patch makes no subsecond PIE claim. Full ABBA rounds, private holdouts, and ranked judging remain outstanding trial-activation work.

## Discussion and attribution

The memory architecture and future bounded-evaluation work are tracked in [Discussion #16](https://github.com/teddyjfpender/stwo-cuda-challenge/discussions/16). This candidate is a narrower measured step for Metal wrap/fold representation and leaf-stream buffers; it does not claim the proposed 50% Cairo memory target.

Model/harness: OpenAI Codex (GPT-6), using the Codex tool harness. Human direction and challenge maintenance: Theodore Pender. No private fixtures, credentials, or proof blobs are included.
