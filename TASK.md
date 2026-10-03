# Task for an optimization agent

## Proof-only CUDA, Metal, and CPU trial

The next challenge epoch measures **only proving intervals** for the same six
PIEs, two recursive folds, and one unique two-leaf PIE-to-root pipeline. Pick
one backend per experiment. CUDA uses an H200; Metal and CPU use the M5 Max.
The historical progress estimates and current PR measurements share the
[main research TSV](data/reports/submission-research-2026-10-03.tsv), but
historical rows are statistical estimates and never rank a submission.

```sh
python3 challenge.py setup-proof --backend cpu --build
# Edit the allowed backend paths under workspace/proof-v2-source/.
python3 challenge.py benchmark-proof --backend cpu \
  --case-id recursion:two-leaf-wrap-fold --out /path/to/local-results \
  --fixtures /path/to/hash-pinned-fixtures
python3 challenge.py capture-proof --backend cpu
```

Choose `metal` or `cuda` in place of `cpu` and see
[the staged proof contract](spec/PROOF_STAGE_EPOCH.md) for timer boundaries,
editable paths, capacity gates, and exact inputs. `setup-proof --build-baseline`
also builds the baseline when it is needed; the first smoke loop builds only
the editable source. `benchmark-proof` checks the exact canonical proof or
root and reports proof-stage time separately from command time. The CUDA
diagnostic requires the H200 assets and independent Rust verifiers from the
[operator runbook](spec/H200_RUNBOOK.md); the M5 path runs locally. Submit
`candidate/proof-v2-changes.patch` in a review PR with the selected backend,
timings, proof hashes, memory, and a short mechanism explanation. This epoch
is in **staging**: trial runs are reviewable research, not ranked receipts.

## Previous H200 command-time contract

Improve CUDA proving of Starknet Cairo PIEs and their recursive aggregation on
one H200. The fixed basket covers standalone PIE proofs, two- and eight-leaf
folds, and two complete PIE → Cairo proof → wrap → fold → root modes. Optimize
adapted-input-to-published-proof time and whole-device peak memory while
preserving every proof, security, and source-policy requirement. All cases and
track guards matter; read [`WORKLOADS.md`](spec/WORKLOADS.md),
[`SCORING.md`](spec/SCORING.md), and
[`SUBMISSIONS.md`](spec/SUBMISSIONS.md) before editing.

Run `python3 challenge.py setup` from the challenge root to create the ignored,
editable prover checkout at **`./workspace/stwo-zig/`** (singular `workspace`).
It is absent from GitHub and fresh clones. Run `python3 challenge.py paths` to
print the absolute local paths. [CODE_MAP.md](spec/CODE_MAP.md) names the exact
files to inspect and edit. The checkout begins with the reviewed
[accepted frontier](frontier/manifest.json)
over the immutable pinned prover source. `challenge.py capture` emits a
**cumulative** patch against the original pin, including the frontier and your
new work; do not strip the inherited changes. To inspect the original baseline
in a fresh checkout, use `challenge.py setup --base`.
The current cumulative frontier is challenge PR #17, including challenge PR #6
and upstream `stwo-zig` PR #205.
After updating challenge `main`, rerun `setup`: an unchanged old frontier
advances automatically. If you have edits, capture your patch first and apply
your changes to a fresh checkout; setup refuses to discard them. PR #17's
direct H200 measurements are unranked research, separate from judge scores.
The five allowed CUDA directories and their purposes are listed in
`spec/SUBMISSIONS.md` and
`benchmark.json`. Use CPU, Metal, and Rust implementations for understanding,
but change production code only in those CUDA directories. The challenge
contract, judge, verifier, fixture manifest, security profile, and reference
outputs are outside the candidate edit surface. `challenge.py capture`
refreshes derived CUDA manifests and writes the restricted
`candidate/changes.patch`; do not hand-edit those manifests or the patch.

Investigate substantial bottlenecks in witness/lookup storage, host/device
transfer, kernel layout, fixed-asset reuse, scheduling, wrap/fold construction,
and publication. Form a falsifiable hypothesis, measure phases and memory,
then test the smallest public case that could disprove it. Use
[GitHub Discussions](https://github.com/teddyjfpender/stwo-cuda-challenge/discussions)
to debate architectures, compare evidence, and share unsuccessful ideas. Link
useful threads from the PR. Discussions are a research channel, not an
alternative to proof checks or a ranked receipt.

Explore several architectural changes before settling on local tweaks. For
each, predict which measured ingress, proof, recursion, or publication phase
should improve, by how much, and at what memory cost. Combine independent
strong changes and measure whether they compose; then refine the surviving
design greedily. A fast PoW or hash primitive that leaves the ten-case command
and memory results unchanged is research evidence, not a winning submission.

Keep the development loop small: focused compile/test, a verified public PIE
and fold/pipeline smoke, repeated idle-host A/B, then complete qualification
when promising. The operator's direct
[`h200_experiment.py`](scripts/h200_experiment.py) records exact identities,
phase times, proof hashes, and peaks; its results are unranked. Standalone Cairo proofs
need the pinned official Rust verifier; pipeline leaves need the pinned
production-registry Rust verifier; every recursive root must bind the correct
contiguous leaves and outputs. Record all regressions and the exact timing
scope. A faster kernel alone is not an end-to-end improvement.

Finish by completing `candidate/NOTES.md`, capturing the patch, and opening a
reviewable PR in this challenge repository. That PR is separate from the
operator's immutable-commit intake and H200 dispatch. The PR must explain the
changed paths, mechanism, before/after public measurements and memory,
correctness checks, tradeoffs, attribution, and related Discussions.
