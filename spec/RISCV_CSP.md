# RISC-V CSP optimization trial

This staged track optimizes full RISC-V guest proofs on an Apple M5 Max. It is
separate from the Cairo/recursion proof-v2 track and has its own pinned source,
editable checkout, measurements, and candidate patch. CPU and Metal are
separate backend lanes. The track uses the existing authenticated
[`stwo-zig` CSP suite](../fixtures/riscv-csp-manifest-v2.json) and
[typed ECDSA precompile manifest](../fixtures/riscv-csp-ecdsa-precompile-v1.json),
both copied byte for byte from the pinned prover source.

The 16 positive cases comprise five SHA-256 messages, five Keccak-256
messages, five Poseidon2-M31 field inputs, and one secp256k1 ECDSA signature.
SHA-256, Keccak-256, and secp256k1 are canonical CSP zkVM workloads.
Poseidon2-M31 is a field-native extension, **not** the BN254 Poseidon2 case on
EthProofs. The ECDSA case uses the typed proved precompile; invalid or
unsupported signatures must take the proved software fallback. The suite
also proves and checks the pinned invalid-signature negative fixture.

## Timing and comparison

The fixed profile is BLAKE3, 70 FRI queries, 26 PoW bits, and no recursion.
The metric is the production CSP report's `proof_duration`: guest execution,
witness construction, and proof generation. Mandatory verification is checked
and timed separately. Loading, building, and the outer command wall time are
diagnostics. Peak physical footprint is a capacity and diagnostic measure.
Do not present the precompile provider's narrower latency as a full guest
proof result.

The direct comparison takes the geometric mean of baseline/candidate
proof-duration ratios within each target, then gives each of the four targets
one quarter of the log weight. Thus the single ECDSA case cannot be buried
under the 15 hash/field rows. This is an **unranked research comparison**.
The CSP script itself independently checks execution counts, statements,
proofs, outputs, negative behavior, backend identity, and power conditions.
The wrapper refuses missing or duplicate cases, changed fixtures, a different
proof suite or security profile, an unproved ECDSA precompile, or cross-host
comparisons. A ranked judge and fresh paired baselines remain to be activated.

These M5 results are internal same-host comparisons. They are **not official
EthProofs ranks**: EthProofs publishes on an AWS `mac2.metal` Apple M1 host.

## Participant workflow

From the challenge repository root:

```sh
python3 challenge.py setup-csp --backend cpu --build-baseline
python3 challenge.py paths-csp --backend cpu
python3 challenge.py benchmark-csp --backend cpu --arm baseline \
  --case sha256:128 --out .runs/csp/baseline-smoke.json
```

Use `--backend metal` for the Metal lane. `setup-csp` creates ignored
`workspace/csp-source` and `workspace/csp-baseline` checkouts at the source
commit in [`benchmark-riscv-csp-v1.json`](../benchmark-riscv-csp-v1.json).
The clean baseline is never edited. `--build` builds only the candidate;
`--build-baseline` builds both checkouts. The suite assets remain inside each
`stwo-zig` checkout and are checked against the challenge's pinned manifests.

Edit only the backend's `editablePaths` under `workspace/csp-source`. The
shared RISC-V frontend, core, protocol, and prover APIs are allowed for both
lanes. The suite manifests, guest binaries, input files, benchmark script,
security settings, and verifier are outside the edit surface. Commit the
source changes **inside that checkout** before benchmarking: the production
CSP benchmark requires a clean implementation commit and binds the binary and
report to it. The wrapper checks the binary's compiled source commit before
starting the matrix, so rebuild with `setup-csp --build` after each commit.
For example:

```sh
git -C workspace/csp-source add src/frontends/riscv
git -C workspace/csp-source commit -m "perf(riscv): describe the improvement"
python3 challenge.py setup-csp --backend cpu --build
python3 challenge.py benchmark-csp --backend cpu \
  --case sha256:128 --out .runs/csp/candidate-smoke.json
```

Start with one target/size to reject weak hypotheses. Omit `--case` for all
16 rows. A complete report defaults to one verified sample per case for a
short research loop; pass `--warmups 1 --samples 10` for a stronger direct
measurement. Run baseline and candidate on an otherwise idle M5 with the same
backend, then compare complete reports:

```sh
python3 challenge.py benchmark-csp --backend cpu --arm baseline \
  --out .runs/csp/baseline.json
python3 challenge.py benchmark-csp --backend cpu --arm candidate \
  --out .runs/csp/candidate.json
python3 challenge.py compare-csp --backend cpu \
  --baseline .runs/csp/baseline.json --candidate .runs/csp/candidate.json \
  --out .runs/csp/comparison.json
python3 challenge.py capture-csp --backend cpu
```

Open a challenge-repository PR containing
`candidate/riscv-csp-changes.patch` and a note with the candidate commit,
changed paths, mechanism, exact verification, per-target proof durations,
command and memory diagnostics, negative-case result, regressions, host/power
conditions, and model/harness attribution. Link any relevant
[GitHub Discussion](https://github.com/teddyjfpender/stwo-cuda-challenge/discussions).
The patch is checked against the immutable source pin and the backend edit
surface; it is reviewable research, not an automatic rank or upstream merge.
Accepted optimizations need an explicit promotion record and an upstream
`stwo-zig` PR so the next frontier stays reproducible.
