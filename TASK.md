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

For Metal, `setup-proof` automatically applies the accepted PR #22 patch to the
editable checkout. Build improvements on that starting point. `capture-proof`
records the full cumulative diff against the pinned source so a reviewer can
reproduce it from a clean checkout; the baseline checkout stays pristine.

For a complete CPU/Metal experiment, run the same basket from
`workspace/proof-v2-baseline` and `workspace/proof-v2-source` into separate
result directories. Export each with `python3 scripts/export_proof_v2.py
--backend BACKEND --root RESULT_DIR --out RESULT.tsv`; the exporter rehashes
every reference proof/root and refuses an incomplete basket. Then run
`python3 challenge.py compare-proof --backend BACKEND --baseline BASELINE.tsv
--candidate CANDIDATE.tsv --out COMPARISON.json`. This single-pass comparison
is unranked; it helps reject weak ideas before expensive paired judging.
