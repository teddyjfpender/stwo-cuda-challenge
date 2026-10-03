# M5 capacity probes on the proposed source pin

These are direct, unranked CPU and Metal capacity probes on `stwo-zig@97510e52`,
the source proposed for the proof-only epoch. All use the exact public compact
CPI and `STWO_CAIRO_COMPACT_POLYNOMIALS=1`; the 25.38M-step CPU case used the
normal 18-worker pool, and the 33.68M-step CPU and Metal cases used four workers
to bound parallel memory. All passed in-process verification and produced the
manifest's exact proof SHA-256. The raw product reports and
[`summary.tsv`](summary.tsv) retain the timings, source pin, configuration,
and physical-footprint peaks.

| Public PIE | Backend | Proof stage | Peak physical footprint |
| --- | --- | ---: | ---: |
| `15591789_15591789`, 25.38M steps | CPU | 113.324 s | 73.62 GB |
| `15588777_15588780`, 33.68M steps | CPU | 203.517 s | 77.98 GB |
| `15588777_15588780`, 33.68M steps | Metal | 216.302 s | 76.84 GB |

The large runs used a disk-space watchdog with a 6 GB stop floor and finished
normally; their lowest observed free disk space was 12.1 GB (CPU) and 13.6 GB
(Metal). A macOS physical
footprint above installed RAM does not mean the proof failed: compression and
swap made both runs complete. It does mean an M5 judge needs an explicit
memory-pressure and swap-headroom gate, plus repeated idle-host timing. These
are single runs, not score denominators or evidence that all remaining public
and private cases already qualify.
