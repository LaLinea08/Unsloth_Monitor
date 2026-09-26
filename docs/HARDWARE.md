# Hardware readings

Hardware readings describe the computer running the monitor and all its
applications. They do not establish model residency, inference activity, or an
inference backend. Collection uses ordinary unprivileged file reads; it launches
no commands, loads no compute runtime, and writes no kernel interfaces.

| Metric | Source and interpretation |
| --- | --- |
| CPU identity | First model name in `/proc/cpuinfo`, cached |
| CPU utilization | Difference between aggregate `/proc/stat` samples; idle and iowait excluded; percentage of whole-machine CPU capacity |
| CPU temperature | Discovered `k10temp`, `coretemp`, or `k8temp` hwmon sensor; prefer Tdie, then Intel package, then Tctl; selected channel is retained in the metric detail |
| RAM | `/proc/meminfo`: used = MemTotal − MemAvailable, a kernel estimate; kB fields converted using 1024 bytes |
| Uptime | First field of `/proc/uptime`, seconds since boot including suspend |
| GPU identity | AMD DRM device product name when available, otherwise local PCI database or exact AMD PCI ID |
| GPU activity | `gpu_busy_percent`, machine-wide percentage |
| VRAM | `mem_info_vram_used` and `mem_info_vram_total`, bytes reported by the driver; on integrated GPUs this is not independent dedicated physical RAM |
| GPU temperature | AMD hwmon `temp1_input`, converted from millidegrees Celsius; channel label preserved |
| GPU / SoC power | AMD hwmon `power1_average`, or `power1_input` if average is absent, converted from microwatts; on APUs this may include CPU power |

The first CPU percentage is pending until a second sample. Counter resets,
including a decreasing iowait counter, require a new baseline. Guest counters are
already included in user/nice and are not counted twice. Missing MemAvailable is
unavailable rather than replaced with a misleading free-memory approximation.
Tctl can be a control value with an offset; it is not always a die temperature.
Each reading retains its source, observation timestamp, unit, and availability.
Cached identity and capacity readings retain their original observation time.

Discovery examines bounded, nonrecursive directory entries once. It selects one
AMD DRM card, preferring the largest reported VRAM capacity, rather than assuming
card0. Restart after GPU hotplug, driver changes, or newly enabled sensors.
Additional GPU views and vendor collectors remain future work. Consumer AMD
cards often lack product_name; a PCI ID is an honest fallback when the optional
local PCI database is absent. No online identity lookup occurs.

Before querying GPU utilization, temperature, or power, the collector checks
`power/runtime_status`. It skips these inputs unless the device is active or
runtime power management is disabled (`unsupported`). Suspended, transitional,
error, unreadable, and unknown states leave these fields unavailable. VRAM
accounting is still read. The state check cannot eliminate a suspend race or prove
no idle-power effect; measure actual drivers on Fedora and CachyOS before making
an overhead claim. Inputs are size-bounded, but Linux driver file reads have no
general userspace timeout, so collection belongs off the GUI thread.

The non-Linux factory returns explicit unsupported metrics. The Windows host
used for initial development only exercises fixtures and Qt smoke tests; this
does not constitute a Windows telemetry port or Linux hardware validation.

Primary references reviewed on 2026-09-26:

- [Linux procfs documentation](https://docs.kernel.org/filesystems/proc.html)
- [AMD GPU sensors and activity](https://docs.kernel.org/gpu/amdgpu/thermal.html)
- [AMD GPU identity and memory accounting](https://docs.kernel.org/gpu/amdgpu/driver-misc.html)
- [AMD CPU temperature semantics](https://docs.kernel.org/hwmon/k10temp.html)
- [Intel coretemp](https://docs.kernel.org/hwmon/coretemp.html)
- [Runtime power state ABI](https://www.kernel.org/doc/Documentation/ABI/testing/sysfs-devices-power)
