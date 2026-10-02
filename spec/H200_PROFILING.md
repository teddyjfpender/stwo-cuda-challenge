# One-case H200 CPU/GPU timeline

Use a timeline to choose a GPU experiment, not to claim a speedup. The CUDA
backend already exposes NVTX ranges for proof stages and has a fail-closed
graph-capture runtime. Whether a particular Cairo, wrap, or fold workload has
launch gaps or can safely reuse a graph is a measurement question. CUDA Graphs
can amortize repeated kernel submission overhead, but graph instantiation,
shape changes, buffer lifetimes, and memory footprint must be included in a
full-path A/B check. See NVIDIA's [CUDA Graphs guide](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/cuda-graphs.html).

On an exclusive, prepared H200, profile one representative PIE and one fold or
pipeline case. Use separate output directories **outside Git**:

```sh
python3 scripts/h200_preflight.py --mode direct --source workspace/stwo-zig
python3 scripts/h200_profile.py --case-id pie:15581148_15581148 \
  --source workspace/stwo-zig --out /operator/profiles/pie-candidate
python3 scripts/h200_profile.py --case-id recursion:two-leaf-wrap-fold \
  --source workspace/stwo-zig --out /operator/profiles/fold-candidate
```

`profile.json` records source and executable digests, preparation time,
profiled command time, ingress subphases, whole-device peak, proof hashes,
and exact verifier results. An NVML `memory_trace.tsv` gives 10 ms whole-device
samples relative to command start, so memory growth can be located alongside
the CPU/GPU timeline. The `.nsys-rep` file and CSV exports include a
GPU trace, kernel summary, CUDA API summary, and NVTX ranges when available.
Use `--lookahead` only when profiling the opt-in integrated multi-PIE path;
the option is recorded in the receipt and remains inside the measured
command. The current public basket has no multi-root campaign, so this tool
cannot assess the separate fixed-host retention experiment.
The profiler holds the same exclusive host lock as the A/B experiment driver,
and refuses a non-idle GPU before profiling.
Nsight Systems follows child processes for pipeline cases on the workstation
edition; inspect the trace to confirm coverage before drawing conclusions.
NVIDIA's [Nsight Systems guide](https://docs.nvidia.com/nsight-systems/UserGuide/index.html)
documents the CUDA/NVTX capture and CSV reports.

Profiling adds substantial overhead. Never compare `profiled_command_s` with
an unprofiled baseline as a performance result. Form a specific hypothesis
from gaps or dominant ranges, change one source path, then use the unprofiled
`h200_experiment.py` repeated A/B gate and exact proof verification. Only run
the ten-case basket after the focused gate passes. For memory changes, compare
whole-device NVML peaks and the resident allocation plan, not just one CUDA
arena. The [Cairo-to-circuit memory audit](H200_MEMORY_AUDIT.md) identifies
the handoff and the first lifetime questions to test. A later resident-service
epoch may report warm proof time; this script
does not invent it or move package creation before the current `.cpi` clock.
