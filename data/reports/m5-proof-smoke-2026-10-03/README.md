# M5 proof-stage qualification smoke

These eight direct, unranked observations use the **same pinned public inputs
and expected proof/root hashes** as `fixtures/public-v1.json`. The source was
the pinned `b2873365` checkout with one local compatibility change: the CPU
and Metal recursive leaf wrapper read canonical compact CPI through
`cairo.adapter.input.readFile` rather than the JSON-only reader. That exact
change is already upstream in `stwo-zig` commit `0301ccfdb`. The local source
diff SHA-256 and both product-binary SHA-256 values are on each row of
[`summary.tsv`](summary.tsv). This overlay is **not** part of the current
challenge pin or accepted frontier.

| Case | CPU diagnostic stage | Metal diagnostic stage | Exact reference output |
| --- | ---: | ---: | :---: |
| Standalone public PIE `15581148_15581148` | 41.179 s | 28.799 s | yes |
| Two distinct leaves, one fold | 6.104 s | 10.585 s | yes |
| Eight distinct leaves, seven folds | 42.627 s | 72.190 s | yes |
| Two adapted PIEs → two wraps → root | 96.464 s | 72.215 s | yes |

The standalone PIE times are the shared Cairo product's `timing.prove_ns`.
Their backend reports and stage profiles are preserved here; the proof bytes
match the manifest, and each CLI's `--verify` check passed. The standalone
process lifetime peak physical footprints were 52.18 GB for CPU and 53.12 GB
for Metal. Both eight-leaf root proofs, output files, and packed trees matched
the manifest exactly.

The fold times are sums of each reduction's logged circuit `prove` duration,
rounded to milliseconds. The serial pipeline number adds the leaf wrapper's
reported Cairo and wrap stages to its fold proof. That wrapper includes some
fixed-asset loading and circuit construction, so **the pipeline numbers are
not yet an isolated proof-only score**. Only the Metal leaf processes had a
separately captured peak RSS; it is not whole-system unified-memory usage and
is not a memory-admission result. Raw logs, Cairo reports, and stage profiles
are retained next to the TSV. No H200 run, paired A/B trial, private holdout,
or ranked judge was performed for these observations.

The smoke establishes that the exact inputs and proof formats can be shared
across backends, and exposes the remaining qualification work. The largest
public PIE has not been run on this 64 GB host; input inspection predicts more
trace storage than the successful PIE, so its capacity must be tested before
the M5 can rank the identical ten-case basket. The Metal fold is slower than
CPU here, and the first reduction's preprocessed commitment took several
seconds; a new epoch needs a trusted timer boundary around the actual proof
for every Cairo, wrap, and fold stage before these diagnostics can become
scores.
