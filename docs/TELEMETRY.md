# Telemetry contract

The monitor reads local operating-system files and one local HTTP liveness
endpoint. It never sends inference requests, loads models, imports a compute
runtime, reads inference logs, or modifies Unsloth. No fixture data is used in
normal operation. Every metric records its source, acquisition timestamp, unit,
availability, and an explanation when missing. Hardware is machine-wide, never
attributed to Unsloth.

## What is implemented

| Measurement | Classification | First prototype |
| --- | --- | --- |
| CPU name/utilization, RAM, uptime | Operating system | Linux procfs; first CPU sample is pending until a baseline exists |
| AMD GPU identity/utilization/VRAM | Operating system | Discovered DRM sysfs device and its readable driver files |
| CPU/GPU temperature, GPU power | Operating system | Accessible hwmon sensors; absent or denied sensors remain unavailable |
| Unsloth service identity/reachability | Verified upstream interface | `GET /api/liveness`; strict `service` and `status` signature |
| Loaded model, quantization, configured context, backend | Not collected by this adapter | Not exposed by the selected passive liveness endpoint |
| Generation state, output-token count/rate, request duration | Not collected by this adapter | No trustworthy request-scoped passive source enabled |

GPU activity is not evidence of generation. An AMD GPU is not evidence of a ROCm
backend. A catalog is not evidence of residency. None of these are inferred.
The liveness `inference_active` hint can cover text or media and omits false values;
the upstream helper also converts failures into false. It is therefore not used
to label this dashboard's model as idle or generating.

## Source evidence, inspected 2026-09-26

The GitHub connector resolved and retrieved official `unslothai/unsloth` source
at commit `b6ee1739d4714193dcba0f3585cb79f839c435ab` (commit date
2026-09-26). This verifies an upstream contract, **not the version installed on
either test computer**. Neither Fedora nor CachyOS was accessible during this
initial Windows development session. No end-to-end Unsloth claim is made.

- [Liveness implementation and media activity helper](https://github.com/unslothai/unsloth/blob/b6ee1739d4714193dcba0f3585cb79f839c435ab/studio/backend/main.py#L1850):
  the liveness route reads existing process state and emits `service: "Unsloth UI
  Backend"` with `status: "alive"`. The monitor accepts that exact signature;
  this is application identification, not cryptographic attestation.
- [Health detection helper](https://github.com/unslothai/unsloth/blob/b6ee1739d4714193dcba0f3585cb79f839c435ab/studio/backend/main.py#L1704):
  `/api/health` can start background hardware detection. It is not probed.
- [Inference status](https://github.com/unslothai/unsloth/blob/b6ee1739d4714193dcba0f3585cb79f839c435ab/studio/backend/routes/inference.py#L19344):
  the status path runs llama-server capability and release-freshness probes.
  It is not polled by this monitor.
- [Loaded-models and catalog routes](https://github.com/unslothai/unsloth/blob/b6ee1739d4714193dcba0f3585cb79f839c435ab/studio/backend/routes/inference.py#L30838):
  `/api/inference/loaded-models` is distinct from `/v1/models`. The catalog
  includes downloaded, unloaded models. Even the loaded-only route's quantization
  helper can [schedule index refreshes](https://github.com/unslothai/unsloth/blob/b6ee1739d4714193dcba0f3585cb79f839c435ab/studio/backend/core/inference/local_model_resolver.py#L1137).
  Neither route is used in this minimal adapter; repeated scans and their hosting
  overhead have not been validated on the user's computer.
- [API monitor route](https://github.com/unslothai/unsloth/blob/b6ee1739d4714193dcba0f3585cb79f839c435ab/studio/backend/routes/inference.py#L19038) and
  [snapshot payload](https://github.com/unslothai/unsloth/blob/b6ee1739d4714193dcba0f3585cb79f839c435ab/studio/backend/core/inference/api_monitor.py#L228):
  recent request records carry prompt/reply previews even with details disabled.
  These routes are not requested. Supporting content-free, scoped inference
  telemetry requires a separately verified interface and explicit metric semantics.

Upstream implementations change. An older installation without `/api/liveness`
will report an unsupported response; the monitor will not silently switch to a
heavier endpoint. The installed version and authentication requirements remain
to be checked directly on CachyOS.

## Connection behavior and bounds

The editable API base defaults to `http://127.0.0.1:8888/v1`; the liveness path
is at the same origin, `/api/liveness`. Only HTTP numeric loopback IPv4/IPv6
addresses and `localhost` are accepted. `localhost` becomes `127.0.0.1` without
DNS. Other hosts, HTTPS, credentials embedded in URLs, custom URL paths, query
strings, and fragments are rejected in this first version. Hardware and Unsloth
must run on the same computer. Remote networking is outside this version.

- One GET per poll, no internal retries, one reusable connection, no proxy or
  environment credential discovery, no redirects.
- Two-second overall request budget, including trickled response headers/body;
  the remaining deadline is checked before each underlying socket read. Body
  retention is capped at 32 KiB. Standard-library HTTP header-count/line limits
  apply. Encoded/compressed response bodies are rejected.
- Closing the client stops further polls, clears its token reference, and
  interrupts pending reads. No helper process or watchdog thread is created.
- A bearer token, if supplied through connection settings, exists in memory only.
  Response bodies, token values, and raw exception messages are never logged or
  retained in snapshots. Network errors use fixed, credential-free explanations.

| Response | Display state |
| --- | --- |
| Exact liveness signature | Online; model/inference fields remain unsupported |
| Other JSON object with HTTP 200 | API reachable, identity unverified |
| HTTP 401 or 403 | Authentication required or access denied |
| Refusal, disconnect, deadline exceeded | Offline/unreachable; not proof of a crash |
| Missing endpoint, redirect, error status, malformed or oversized payload | Unsupported response |

No-model-loaded is deliberately not reported: liveness cannot establish that
condition. A failed poll clears unavailable values rather than showing old
measurements as current. The UI's scheduler owns refresh intervals and backoff;
hardware collection runs independently.

## Read-only check on CachyOS

From a complete source checkout, run `python3 scripts/diagnose.py`. Python 3.11+
and the standard library suffice; it does not install dependencies or import Qt.
It samples this computer's actual Linux hardware and performs one bounded GET to
the liveness endpoint. Output contains selected readings and states, the OS
version, Python version, and timestamps. It excludes hostname, raw server
responses, credentials, prompts, replies, and model files. Review the output
before sharing it. Redirect output to a private file only if wanted; the script
itself writes no files.

If authentication is required, set a token privately in an environment variable
and pass its **name** using `--token-env VARIABLE`; do not put the token on the
command line or paste it into chat. `--base-url` accepts another local HTTP port.
This diagnostic cannot identify the installed Unsloth version from liveness;
record that version separately from the application's own About/version display.

Automated local HTTP tests use synthetic payloads exclusively inside tests.
They cover schema/identity rejection, credential-safe errors, authentication,
refusal/start/restart, persistent connections, body limits, trickle deadlines,
and cancellation. They do not establish real Unsloth compatibility, sensor
accuracy, Linux distribution support, or hosting performance impact.
