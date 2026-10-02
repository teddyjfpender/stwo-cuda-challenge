# Cairo-to-circuit device-memory audit

This source-level audit identifies what a whole-device H200 trace must
confirm. It does **not** claim a measured peak reduction.

In `workspace/stwo-zig/src/products/cairo_cuda/app.zig`, each Cairo proof
prepares one combined arena whose slot placement already aliases request and
process lifetimes. Its arena key binds the geometry and resident plan. For a
verified recursive leaf, `proveOnce` calls `releasePreparedExecution()`
**before** invoking the circuit receiver, then clears the cached static
receipt. The large Cairo arena should therefore not coexist with the circuit
proof arena. The receiver and integrated fold use the same CUDA runtime, so
CUDA context, loaded modules, and any explicitly retained device image remain
live across that handoff.

In `src/products/circuit_recursion_cuda/main.zig`, the default integrated
batch drops the 2.17 GB **host** fixed snapshot after all Cairo leaves and
before parsing and folding the root. Merged upstream PR #205 can retain it across
campaign roots; that changes host RSS and reread time, not device capacity.
The source lookahead in that draft keeps one next PIE's prepared CPU request
alive while the current leaf proves. It admits compact CPI files of at most
64 MiB, but prepared geometry and witness data may still raise host RSS.
Both options stay inside the measured command.

The optional static `DeviceImage` can persist in a `BatchSession` until its
deinitialization. The current direct challenge environment does not enable
`STWO_CAIRO_CUDA_STATIC_IMAGE`, so it is not a presumed cause of public
pipeline peaks. If a future candidate enables it, compare the avoided reload
time with its extra live device bytes at the leaf wrap and fold boundary.
Freeing the image before a fold is a capacity hypothesis, not a safe default
without repeated exact-proof and whole-device measurements.

Use [`H200_PROFILING.md`](H200_PROFILING.md) for one PIE and the integrated
two-leaf pipeline. Read `memory_trace.tsv` and the NVTX/CUDA timeline together
with `planned_arena_bytes` from `profile.json`. The questions are:

1. Does the whole-device peak occur inside Cairo proof work, during the
   prepared-arena release and circuit handoff, or in the fold?
2. Does the observed peak fall when the Cairo arena is released, and by how
   much? A high planned arena alone does not prove other allocations overlap.
3. Are context/module caches, a static device image, circuit AOT buffers, or
   delayed frees the remaining live allocations at the handoff?
4. On near-capacity PIEs, does a lifetime change preserve the exact proof and
   stay inside the physical H200 reserve on every case?

Run the unprofiled, verified A/B gate after a specific buffer-lifetime edit;
Nsight time is diagnostic. A device-memory win must be shown by whole-device
NVML peaks and the exact resident plan, not just a smaller arena field. The
current public basket has no multi-root campaign case, so cross-root host
retention needs a separate, explicitly unranked diagnostic before adoption.
