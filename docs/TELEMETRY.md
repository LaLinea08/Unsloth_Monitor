# Telemetry contract

The monitor reads local operating-system files, a local HTTP liveness endpoint,
and an optional in-memory operation registry. It never sends inference requests, loads models, imports a compute
runtime, reads inference logs, or modifies Unsloth. No fixture data is used in
normal operation. Every metric records its source, acquisition timestamp, unit,
availability, and an explanation when missing. Hardware is machine-wide, never
attributed to Unsloth.

## What is implemented

| Measurement | Classification | Implementation |
| --- | --- | --- |
| CPU name/utilization, RAM, uptime | Operating system | Linux procfs; first CPU sample is pending until a baseline exists |
| AMD GPU identity/utilization/VRAM | Operating system | Discovered DRM sysfs device and its readable driver files |
| CPU/GPU temperature, GPU power | Operating system | Accessible hwmon sensors; absent or denied sensors remain unavailable |
| Unsloth service identity/reachability | Verified upstream interface | `GET /api/liveness`; strict `service` and `status` signature |
| In-flight operation count and active model labels | Verified upstream interface | `GET /api/inference/active-generations`, after verified liveness; account-scoped and only when supported/authenticated |
| Loaded model, quantization, configured context, backend | Not collected by this adapter | Not exposed by the selected passive interfaces |
| Decode-only generation state, output-token count/rate, request duration | Not collected by this adapter | No suitable content-free, request-scoped source enabled |

GPU activity is not evidence of generation. An AMD GPU is not evidence of a ROCm
backend. A catalog is not evidence of residency. None of these are inferred.
The liveness `inference_active` hint can cover text or media and omits false values;
the upstream helper also converts failures into false. It is therefore not used
to label this dashboard's model as idle or generating.

### Operation count and model labels

The activity route reports operations visible in the server's account-scoped
in-flight registry (legacy single-account installations use installation-wide
scope). Its lifetime can include loading, admission queue waits,
tool calls, and embeddings as well as text decoding. Therefore the dashboard
labels it **In-flight operations**, never decode-only generation. A zero count
means no operations were reported by that registry at this sample; it does not
establish that all engines are idle or no model is loaded. Other accounts and
untracked work may not be visible.

Model labels belong to these operations. They can name a requested model before
it finishes loading. They are shown as **Active model labels**, not a resident
model inventory; they clear when operations finish. Up to three distinct labels
are shown, with a count of additional labels; the operation count always covers
the complete accepted registry response. Run, conversation, handle, and account
identifiers are discarded. No prompt, reply, error log, or model file is requested.
An empty model label list is unavailable, never an invented model.

This adds useful live activity without turning a queue/tool phase into a tokens/s
reading. Quantization, configured context, actual backend, and request token
statistics remain unavailable until a suitable passive interface is verified.

## Source evidence, inspected 2026-09-26

Official `unslothai/unsloth` source was rechecked at commit
`8faa867ff7396f01bc33a19a183d5be51bd7a4c2`, after the initial liveness review at
`b6ee1739d4714193dcba0f3585cb79f839c435ab`. This verifies an upstream contract,
**not the version installed on either test computer**. The user's screenshot
shows the previous monitor online with AMD readings on the CachyOS machine;
it does not establish activity-route availability or authentication. No direct
access to either Linux computer was available during this Windows development.

- [Liveness implementation and media activity helper](https://github.com/unslothai/unsloth/blob/8faa867ff7396f01bc33a19a183d5be51bd7a4c2/studio/backend/main.py#L1878):
  the liveness route reads existing process state and emits `service: "Unsloth UI
  Backend"` with `status: "alive"`. The monitor accepts that exact signature;
  this is application identification, not cryptographic attestation.
- [Activity route](https://github.com/unslothai/unsloth/blob/8faa867ff7396f01bc33a19a183d5be51bd7a4c2/studio/backend/routes/inference.py#L15467)
  and [registry](https://github.com/unslothai/unsloth/blob/8faa867ff7396f01bc33a19a183d5be51bd7a4c2/studio/backend/state/active_generations.py#L129):
  the GET takes an in-memory snapshot and reads existing slot attributes. It
  does not scan model directories, start model loads, run probes, or return
  inference content. Registration can precede loading; requested model labels
  and count are consequently described with that limited meaning.
- [Authentication](https://github.com/unslothai/unsloth/blob/8faa867ff7396f01bc33a19a183d5be51bd7a4c2/studio/backend/auth/authentication.py#L312)
  accepts Studio session JWTs and valid `sk-unsloth` API keys through the same
  bearer-token setting. The handler's in-memory reads still pass through normal
  server authentication and account-storage checks. In particular,
  [API-key validation](https://github.com/unslothai/unsloth/blob/8faa867ff7396f01bc33a19a183d5be51bd7a4c2/studio/backend/auth/storage.py#L1765)
  updates that key's `last_used_at` in Unsloth's SQLite database on each request.
  A Studio session JWT avoids this specific API-key bookkeeping, but may expire.
  The monitor neither writes that database directly nor changes authentication
  settings. Passive HTTP reads are not a promise of zero server disk activity.
- [Health detection helper](https://github.com/unslothai/unsloth/blob/8faa867ff7396f01bc33a19a183d5be51bd7a4c2/studio/backend/main.py#L1926):
  `/api/health` can start background hardware detection. It is not probed.
- [Inference status](https://github.com/unslothai/unsloth/blob/8faa867ff7396f01bc33a19a183d5be51bd7a4c2/studio/backend/routes/inference.py#L19508):
  the status path runs llama-server capability and release-freshness probes.
  It is not polled by this monitor.
- [Loaded-models and catalog routes](https://github.com/unslothai/unsloth/blob/8faa867ff7396f01bc33a19a183d5be51bd7a4c2/studio/backend/routes/inference.py#L30838):
  `/api/inference/loaded-models` is distinct from `/v1/models`. The catalog
  includes downloaded, unloaded models. Even the loaded-only route's quantization
  helper can [schedule index refreshes](https://github.com/unslothai/unsloth/blob/8faa867ff7396f01bc33a19a183d5be51bd7a4c2/studio/backend/core/inference/local_model_resolver.py#L1137).
  Neither route is used in this minimal adapter; repeated scans and their hosting
  overhead have not been validated on the user's computer.
- [API monitor route](https://github.com/unslothai/unsloth/blob/8faa867ff7396f01bc33a19a183d5be51bd7a4c2/studio/backend/routes/inference.py#L19038) and
  [snapshot payload](https://github.com/unslothai/unsloth/blob/8faa867ff7396f01bc33a19a183d5be51bd7a4c2/studio/backend/core/inference/api_monitor.py#L228):
  recent request records carry prompt/reply previews even with details disabled.
  These routes are not requested. Supporting content-free, scoped inference
  token telemetry requires a separately verified interface and explicit metric semantics.

Upstream implementations change. An older installation without `/api/liveness`
will report an unsupported response; the monitor will not silently switch to a
heavier endpoint. An absent, denied or changed activity route leaves only its
fields unavailable and preserves successful liveness. Installed-version activity
support and authentication remain to be checked directly on CachyOS.

## Connection behavior and bounds

The editable API base defaults to `http://127.0.0.1:8888/v1`; the liveness path
is at the same origin, `/api/liveness`. Only HTTP numeric loopback IPv4/IPv6
addresses and `localhost` are accepted. `localhost` becomes `127.0.0.1` without
DNS. Other hosts, HTTPS, credentials embedded in URLs, custom URL paths, query
strings, and fragments are rejected in this first version. Hardware and Unsloth
must run on the same computer. Remote networking is outside this version.

- One liveness GET per poll and, only after its exact signature is verified,
  one optional activity GET. No internal retries, one reusable connection, no
  proxy or environment credential discovery, no redirects. Requests follow the
  chosen interval (five seconds normally; 30 in quiet mode).
- One shared two-second overall budget for both requests, including trickled response headers/body;
  the remaining deadline is checked before each underlying socket read. Body
  retention is capped at 32 KiB per response. Activity responses above 256 entries
  are rejected instead of silently truncated. Standard-library HTTP header-count/
  line limits apply. Encoded/compressed response bodies are rejected.
- Closing the client stops further polls, clears its token reference, and
  interrupts pending reads. No helper process or watchdog thread is created.
- A bearer token, if supplied through connection settings, exists in memory only.
  Response bodies, token values, and raw exception messages are never logged or
  retained in snapshots. Network errors use fixed, credential-free explanations.

| Response | Display state |
| --- | --- |
| Exact liveness signature | Online; activity checked separately |
| Other JSON object with HTTP 200 | API reachable, identity unverified |
| HTTP 401 or 403 | Authentication required or access denied |
| Refusal, disconnect, deadline exceeded | Offline/unreachable; not proof of a crash |
| Missing endpoint, redirect, error status, malformed or oversized payload | Unsupported response |

The table describes liveness. For the optional activity request, 401/403 makes
its metrics permission-denied and suggests the session-only token setting;
404/changed schema/oversized data is unsupported, and timeouts are unavailable.
These responses keep the verified service status online. Press `d` for each
metric's explanation. No previous activity/model label is kept as current after
an unsuccessful activity poll.

No-model-loaded is deliberately not reported: these interfaces cannot establish
that condition. A failed poll clears unavailable values rather than showing old
measurements as current. The UI's scheduler owns refresh intervals and backoff;
hardware collection runs independently.

## Read-only check on CachyOS

From a complete source checkout, run `python3 scripts/diagnose.py`. Python 3.11+
and the standard library suffice; it does not install dependencies or import Qt.
It samples this computer's actual Linux hardware and performs a bounded liveness
GET followed, when verified, by the activity GET within the same deadline. Output
contains selected readings and states, active-operation model labels when
available, the OS version, Python version, and timestamps. It excludes hostname,
raw server responses, account/conversation/run IDs, credentials, prompts, replies,
and model files. Model labels may be private; review the output
before sharing it. Redirect output to a private file only if wanted; the script
itself writes no files.

If authentication is required, use a Studio session token or an existing Unsloth
API key. The interactive monitor's `s` setting keeps it hidden and in memory only.
For the diagnostic, set the token privately in an environment variable
and pass its **name** using `--token-env VARIABLE`; do not put the token on the
command line or paste it into chat. `--base-url` accepts another local HTTP port.
This diagnostic cannot identify the installed Unsloth version from liveness;
record that version separately from the application's own About/version display.

Automated local HTTP tests use synthetic payloads exclusively inside tests.
They cover schema/identity rejection, credential-safe errors, authentication,
refusal/start/restart, persistent connections, activity auth/failure isolation,
count/schema validation, identifier discard, finishing operations, body limits,
shared/trickle deadlines, and cancellation in both requests. They do not establish real Unsloth compatibility, sensor
accuracy, Linux distribution support, or hosting performance impact.
