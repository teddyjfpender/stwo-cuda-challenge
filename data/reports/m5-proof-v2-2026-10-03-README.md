# M5 proof-v2 direct smoke, 2026-10-03

The companion [summary TSV](m5-proof-v2-2026-10-03-summary.tsv) records one
two-leaf fold each on CPU and Metal from the proposed proof-v2 source commit.
Both outputs matched the pinned proof, public outputs, and packed statement
byte for byte. The hash-checked timer surrounded the fold prover call and
reported 5.966419458 s on CPU and 11.279791500 s on Metal. Full command
times are retained separately; neither is a score denominator.

This is a single, unsandboxed smoke on the M5 Max, not a paired baseline,
ranking, or cross-backend performance claim. The TSV records source/timer
identities and SHA-256 hashes of the local receipts and exact outputs. The
full nine-case basket, independent verifier gate, holdouts, and memory
admission are still required before a ranked epoch can open.
