# Stwo proving challenge

Optimize **proof execution** for the same nine hash-pinned Starknet jobs on CUDA H200, Metal M5 Max, or CPU M5 Max. Six jobs prove Cairo PIEs, two fold already wrapped leaves, and one proves two PIEs through Cairo, wrap, and fold to a single root. Choose one backend per submission. Each backend has its own source edit surface and baseline; only its Cairo, wrap, and fold prover-call intervals enter the proposed latency score. Input loading, setup, publication, verification, and full-command time are separate diagnostics. Memory must fit the selected host and does not multiply the score.

The proof-only epoch is **staging**. Participants can build, run exact public jobs, capture a reviewable patch, and open a PR now. Direct measurements are unranked until the paired, isolated judge, independent verification, and full backend baselines qualify. The prior H200 command-time contract is [archived](spec/LEGACY_H200_V1.md); its old numbers are not proof-only ranks.

## Start a trial

Read [TASK.md](TASK.md), the [proof contract](benchmark-proof-v2.json), [fixed jobs](fixtures/public-proof-v2.json), and [submission guide](spec/SUBMISSIONS.md). Clone this repository, then run:

```sh
git lfs pull
python3 challenge.py check-data
python3 challenge.py setup-proof --backend metal --build
python3 challenge.py benchmark-proof --backend metal \
  --case-id recursion:two-leaf-wrap-fold --out ./proof-trial
```

Replace `metal` with `cpu` on the M5 Max, or `cuda` on a prepared H200. The editable pinned prover checkout appears at `workspace/proof-v2-source`; the clean reference checkout is `workspace/proof-v2-baseline`. Both are ignored by Git. For CUDA, prepare fixed assets and independent Rust verifiers using the [H200 runbook](spec/H200_RUNBOOK.md). Run a representative PIE and fold before omitting `--case-id` for the full nine-job basket. Each direct receipt records source and binary identities, exact reference output checks, proof time, and command time separately. The [epoch design](spec/PROOF_STAGE_EPOCH.md) specifies stage boundaries and remaining activation gates.

For CPU/Metal, `scripts/export_proof_v2.py` rechecks every on-disk proof or root
and exports the complete direct basket to TSV. After running the baseline and
candidate separately, `challenge.py compare-proof --backend metal --baseline
BASELINE.tsv --candidate CANDIDATE.tsv --out COMPARISON.json` gives an
**unranked** family-weighted proof-time comparison. This is a quick research
loop, not the paired, isolated rank judge.

Explore architectural improvements first, measure whether strong changes compose, then refine the best design. Use [GitHub Discussions](https://github.com/teddyjfpender/stwo-cuda-challenge/discussions) to compare designs and report useful failed experiments. After editing only the selected backend's `editablePaths` in the contract, run `python3 challenge.py capture-proof --backend metal`. Commit `candidate/proof-v2-changes.patch` and your notes in a challenge-repository PR. Include the changed source paths, mechanism, before/after proof-stage times, exact proof checks, memory and command diagnostics, regressions, attribution, and relevant Discussions. The [participant skill](skills/stwo-cuda-challenge/SKILL.md) gives the same workflow to coding agents.

## Data and website

The [main research TSV](data/reports/submission-research-2026-10-03.tsv) places historical modeled PIE improvements and measured direct observations against the same six current public inputs. `record_kind`, provenance, method, and uncertainty fields distinguish modeled history from measurements; neither is a signed proof-v2 rank. The [site source manifest](data/site/sources.json) points the website to this TSV, the proof contract, fixed jobs, and backend observation tables. [CUDA](https://autoresearch-web-lac.vercel.app/challenges/stwo-cuda), [Metal](https://autoresearch-web-lac.vercel.app/challenges/stwo-metal), and [CPU](https://autoresearch-web-lac.vercel.app/challenges/stwo-cpu) share the job definitions and show backend-specific observations.

The [activation record](spec/ACTIVATION.md) lists what remains before promotion can issue ranked receipts. Source changes belong in the upstream [`stwo-zig`](https://github.com/teddyjfpender/stwo-zig) prover; this repository pins that source and stores participant patches, harnesses, manifests, and research data.
