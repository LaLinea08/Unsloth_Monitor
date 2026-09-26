# Performance validation

The performance numbers below are engineering targets, not achieved claims.
No inference benchmark has been authorized or run. No Fedora, CachyOS, packaged
Linux, Wayland, or X11 overhead result has yet been recorded.

| Target at default visible refresh | Interpretation |
| --- | --- |
| Steady-state resident memory ≤100 MiB | Include monitor helper processes; investigate sustained usage above 150 MiB |
| Average CPU <0.5% of one logical CPU | Do not divide by the machine's logical CPU count and call that the same quantity |
| Lower minimized overhead | Poll at 30 seconds and suppress dashboard updates |
| Bounded long-session memory | Single result slot per source, no persistent sample history; verify over hours |
| No repeatable inference regression beyond noise | Requires separately authorized, controlled tests on the packaged CachyOS application |

## Implemented controls

The dashboard uses native widgets, no animations or graphs, and changes labels
and progress values only when necessary. Hardware and HTTP run in two persistent
workers with no executor queues, helper command loop, or overlapping polls.
Static hardware discovery is cached. The default refresh is five seconds plus
collection duration; minimized polling is 30 seconds. Failed HTTP checks back
off to 30 seconds, and each request has a two-second overall budget. The process
does not persist samples or write diagnostic logs on each refresh.

The runtime package excludes ML frameworks. GPU compute is never initialized by
the monitor. Window rendering/compositing can still consume graphics resources.
GPU runtime-state guards skip optional sensors on suspended devices, but they do
not establish that polling active devices has zero power or latency impact.

## Measuring monitor overhead

`scripts/measure_overhead.py` observes the monitor process tree using the
development-only `psutil` dependency. It launches a separate monitor instance
with an isolated temporary configuration, waits through a warm-up, then samples
resident memory and cumulative CPU time at one-second intervals. It sends no
inference prompts and performs no inference benchmark. The launched monitor
still makes its normal passive local liveness checks.

From the isolated development environment:

```bash
python scripts/measure_overhead.py --warmup 10 --duration 300
python scripts/measure_overhead.py --warmup 10 --duration 300 --minimized
```

For a candidate package, supply `--executable /absolute/path/to/the.AppImage`.
Use `--offscreen` only for a headless engineering check and identify it explicitly
in the results. It cannot substitute for a normal visible desktop session.

Output separates sampled startup memory from steady-state samples and reports
mean/peak/first/last RSS, CPU relative to one logical CPU, peak observed process
count, and clean exit. The observer itself is excluded; short-lived helpers may
be missed between samples. Startup peaks are sampled estimates. Record exact OS,
kernel, CPU/GPU, Python/Qt/package versions, display session, visibility, refresh,
service state, duration, and other workload. Preserve raw outputs privately and
commit only a reviewed summary without credentials or private machine logs.

## Results register

| Run | Result |
| --- | --- |
| Windows 11 build26200 AMD64, Python3.14.6 / Qt6.11.2, offscreen source, default polling, unsupported hardware collector, offline endpoint | 10s warm-up;59.23s measured; mean tree RSS64.46MiB, peak64.48MiB, first64.46MiB,last64.41MiB; startup sampled peak64.45MiB;2 processes;clean exit |
| Fedora visible/minimized source prototype | Not run |
| CachyOS visible/minimized packaged application | Not run |
| Hours-long memory observation | Not run |
| GPU idle-power / graphics-memory comparison | Not run |
| Inference throughput / time-to-first-token comparison | Not authorized or run |

## Later inference comparison

The Windows run's CPU counter delta reported 0.000% of one logical CPU at the
observer's precision. Interpret this as below measurement resolution, never as
zero overhead. It used the offscreen renderer without a populated font database,
not the Linux collector or a native display/compositor. This very short run does
not establish the visible Linux targets or long-session memory behavior. The two
processes include the Windows virtual-environment launcher and interpreter.

Obtain explicit authorization before running any prompts or benchmark. On
CachyOS, compare monitor closed, packaged monitor visible at defaults, and
optionally minimized. Keep the model, backend, context, prompt, generation
settings, concurrency, and other workload constant. Warm up, repeat runs, and
report normal variation alongside throughput and time to first token when
available. Include the monitor process tree's CPU/RSS and relevant GPU memory
and idle-power differences. Investigate a repeatable throughput loss above
approximately 1% only when it is distinguishable from normal variation. An
inconclusive comparison is not evidence of no impact.
