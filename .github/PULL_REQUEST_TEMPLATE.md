## CUDA change

Describe the bottleneck, the mechanism, and the CUDA paths changed. Include
the relevant `candidate/changes.patch` and completed `candidate/NOTES.md`.
List the architecture alternatives considered, the expected affected stage
and minimum full-command gain, the smallest falsifying case, any independent
wins combined, and why this design survived before local tuning.

## Evidence

| Public case | Before time / peak bytes | After time / peak bytes | Runs and proof checks |
| --- | --- | --- | --- |
| | | | |

State the hardware, source commit, security profile, verification result,
regressions, sample count, exact timing boundary, and whole-device memory
method. Include the focused PIE and fold/pipeline smoke, any A/B gate result,
and the complete basket if run. Local measurements are research
evidence; only a signed H200 rank receipt establishes a leaderboard result.
Do not paste API keys, private fixture identifiers, unpublished inputs, or
proof blobs.

## Design discussion and attribution

Link relevant Ideas, Q&A, or Show and tell Discussions. What alternatives or
tradeoffs did the discussion reveal? Name any model or coding harness used and
the human/code contributors.

## Submission identity

- Immutable submitted fork commit SHA:
- Intake submission ID, when available:
- Signed public receipt link, when available:

Opening this PR does not start the H200 judge. For this internal challenge,
the operator reviews and freezes the PR head with `service/pr_batch.py`;
see `spec/SUBMISSIONS.md`.
