# Performance validation

The following are engineering targets, not achieved claims. The current app is
terminal-native. No terminal application overhead, actual Fedora/CachyOS,
packaged Linux, long-session, or inference-impact result is established yet.
No inference benchmark was authorized or run.

| Target | Interpretation |
| --- | --- |
| Steady-state resident memory ≤100 MiB | Include monitor helpers; investigate sustained usage above 150 MiB |
| Average CPU <0.5% of one logical CPU | Do not substitute CPU divided by the whole-machine logical CPU count |
| Lower quiet-mode overhead | Explicit 30-second polling; terminal minimization cannot be reliably detected |
| Bounded long-session memory | Single result slot per source, no sample history; verify over hours |
| No repeatable inference regression beyond noise | Requires separately authorized tests of the packaged CachyOS application |

## Implemented controls

The runtime has no Qt, browser, ML, or inference dependencies. Two persistent
workers collect hardware and HTTP independently with no overlapping polls or
unbounded executor queues. Discovery is cached. Normal polling defaults to five
seconds plus collection time; `p` or `--quiet` selects 30 seconds. Failed HTTP
checks back off to 30 seconds, with a two-second overall budget per request.

The terminal input loop wakes at most twice per second and does not redraw
unchanged frames. There are no animations, charts, sample history, or background
sample-log writes. GPU compute is never initialized. Terminal emulator
rendering/compositing can still use graphics resources and must be considered.
GPU runtime-state guards do not establish zero wake or idle-power impact.

## Measuring the current implementation

Use the development-only psutil observer from an isolated environment. It sends
no inference prompts. Normal monitor liveness checks still occur.

```bash
python scripts/measure_overhead.py --warmup 10 --duration 300
python scripts/measure_overhead.py --warmup 10 --duration 300 --quiet
```

These commands start a monitor in a synthetic Linux pseudo-terminal with an
isolated temporary configuration. Add `--executable /absolute/path/to/the.AppImage`
for a candidate package. A synthetic PTY excludes terminal-emulator rendering
and is only an engineering baseline.

For an application already open in the user's normal terminal, observe its PID:

```bash
python scripts/measure_overhead.py --pid MONITOR_PID --warmup 10 --duration 300
```

This leaves the existing monitor running and uses its current settings. Its
parent terminal emulator is outside the monitor process tree: record the
terminal's incremental CPU/memory separately when evaluating total overhead.
Do not count all pre-existing terminal memory as newly caused by the monitor.

Output separates sampled startup memory from steady-state samples and reports
mean/peak/first/last process-tree RSS, CPU relative to one logical CPU, and peak
observed process count. Sampling occurs once per second; short-lived helpers
and subsecond peaks may be missed. The observer is excluded. Synthetic-PTY runs
check clean monitor exit; PID observation intentionally leaves the process open.

Record OS/kernel, CPU/GPU, package/Python versions, terminal emulator/version,
TERM, display session, terminal dimensions, polling mode, Unsloth service state,
duration, and other workloads. Keep raw logs private and commit only reviewed
summaries without credentials or inference content.

## Results register

| Run | Result |
| --- | --- |
| Initial terminal package `edbd92d`, default mode, synthetic PTY | 21.89 MiB mean tree RSS; 21.91 MiB peak; 0.219% of one logical CPU; 59.25 s measured after 10 s warm-up; one process; clean exit |
| Initial terminal package `edbd92d`, quiet mode, synthetic PTY | 21.90 MiB mean tree RSS; 21.91 MiB peak; 0.219% of one logical CPU; 59.25 s measured after 10 s warm-up; one process; clean exit |
| Final terminal package `abc2b39`, default mode, synthetic PTY | 21.96 MiB mean/peak tree RSS; 0.219% of one logical CPU; 59.25 s measured after 10 s warm-up; one process; clean exit |
| Final terminal package `abc2b39`, quiet mode, synthetic PTY | 21.89 MiB mean/peak tree RSS; 0.051% of one logical CPU; 59.24 s measured after 10 s warm-up; one process; clean exit |
| Current terminal runtime, actual Fedora terminal | Not run |
| Packaged application, CachyOS normal/quiet modes | Not run |
| Hours-long memory observation | Not run |
| GPU idle-power / graphics-memory comparison | Not run |
| Inference throughput / time-to-first-token comparison | Not authorized or run |

Earlier Windows offscreen Qt observations, if retained elsewhere, describe the
superseded GUI. They cannot demonstrate current terminal performance.

The initial terminal observations ran on Ubuntu 22.04, kernel 6.8.0-1064-azure,
x86_64/glibc 2.35; bundled Python 3.11.16; TERM=xterm-256color, 32×100 synthetic
PTY; default offline loopback endpoint; no target AMD GPU. The observer sampled
once per second. Both runs were stable over this short interval, but did not
demonstrate lower CPU in quiet mode. Idle UI wakeups were subsequently reduced
from 500 ms to 2000 ms in quiet mode; the final runs above use that refinement
in the same CI environment. Keyboard input still wakes immediately. These are
preliminary process figures, excluding terminal-emulator rendering; they are
not a packaged CachyOS hosting-impact result or a long-session guarantee.

The final package source is `abc2b392e892d01997fdc5f0106407a81a34d750`.
[Build and observation evidence](https://github.com/LaLinea08/Unsloth_Monitor/actions/runs/36264025155)
includes the raw reviewed JSON as temporary workflow artifacts. Normal-mode RSS
was 21.95 MiB at the first steady sample and 21.96 MiB at the last; quiet-mode RSS
was 21.88 MiB then 21.89 MiB. Startup sampled peaks were 21.95 and 21.88 MiB,
respectively. These are single short runs, not statistical hosting comparisons.

## Later inference comparison

Obtain explicit authorization before sending benchmark prompts. On CachyOS,
compare monitor closed, packaged monitor at defaults in the normal terminal,
and quiet mode where useful. Keep the model, backend, context, prompt,
generation settings, concurrency, and other workload constant. Warm up, repeat
runs, and report variation together with throughput and time to first token
where available. Include monitor/terminal CPU and memory plus GPU memory and
idle-power differences. Investigate a repeatable throughput reduction above
approximately 1% only when distinguishable from ordinary variation. Inconclusive
results are not evidence of no impact.
