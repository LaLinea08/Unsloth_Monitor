# Release automation request — 2026-09-26

The user requested a release each time so that only one file is downloaded.
Prepare a development prerelease after each successful trusted-branch Linux
package build, with one AppImage asset and checksum/test evidence in its notes.
Public publication remains gated pending explicit resolution of the earlier
license hold; no project license has been selected. Include third-party notices
and source provenance. Fedora/CachyOS and stable acceptance remain pending.

# Current user-approved interface amendment — 2026-09-26

The user explicitly changed the interface requirement during implementation:
**“Run inside my normal terminal and inherit its appearance.”**

This supersedes the original graphical-widget/Qt preference and prohibition on
terminal rendering below. The primary application is now a Linux curses terminal
dashboard using the host terminal's default foreground/background, font, palette
and transparency. Do not imitate a fixed terminal theme in a Qt window. Keep all
passive monitoring, accuracy, manual-launch, Linux-first and release constraints.
Do not bundle Qt in the primary package. Terminal minimization is not portably
observable; provide an explicit quiet mode with reduced polling and document it.

The original complete brief is retained below for all other requirements.

---

You are Codex. Help me build a real desktop application called “Unsloth Monitor”.

This is the complete project specification. Read it before starting, inspect the existing workspace, and then begin implementing the project.

I am starting development on my Fedora PC, where Codex is installed. My separate CachyOS AI PC will be used for Unsloth integration and performance testing.

I want a working application—not a list of existing monitoring tools, a browser dashboard, a visual mockup, or only an implementation plan.

1. PROJECT GOAL AND PRIORITIES

Build a lightweight desktop companion for Unsloth Desktop that displays:
- Live hardware statistics.
- Verified Unsloth connection and model information.
- Inference statistics wherever they can be obtained reliably.

Develop and release it for Linux first, targeting as many mainstream distributions as reasonably possible. Add Windows support afterward.

Maintain the complete project on my GitHub, including source code, documentation, tests, packaging, build workflows, and downloadable releases.

Priority order:
1. Do not interfere with AI hosting or alter the system.
2. Show truthful, verified information.
3. Keep resource usage minimal and measured.
4. Deliver a stable, easy-to-install Linux application.
5. Provide a clean industrial interface.
6. Add optional features and Windows support afterward.

No application code or repository has been delivered in this conversation. However, inspect the actual workspace and repository state before assuming that nothing exists.

2. DEVELOPMENT AND TEST COMPUTERS

DEVELOPMENT COMPUTER

Operating system: Fedora Linux.
CPU: AMD Ryzen 7 9800X3D.
GPU: AMD Radeon RX 9070 XT.
Codex is installed here.

Use this computer for:
- Writing code.
- Developing the interface.
- Running automated tests.
- Testing local hardware collectors.
- Building initial Linux packages.
- Measuring preliminary application overhead.

Inspect the actual environment rather than assuming package versions, desktop session, dependencies, or tool availability.

Do not assume that Unsloth is installed or running on Fedora.

PRIMARY INTEGRATION AND PERFORMANCE TEST COMPUTER

Operating system: CachyOS.
Desktop environment: KDE Plasma with Wayland.
CPU: AMD Ryzen 5 5600X.
Motherboard: MSI B550-A PRO.
GPU: AMD Radeon RX 9060 XT with 16 GB VRAM.
System RAM: 16 GB.
Unsloth Desktop is installed on this computer.

Expected local OpenAI-compatible API base URL:

http://127.0.0.1:8888/v1

Verify the actual address, installed Unsloth version, authentication requirements, and supported interfaces.

These are two separate computers. Do not mix their hardware, measurements, logs, or test results.

127.0.0.1 on Fedora refers to Fedora, not the separate CachyOS computer.

For the first end-to-end integration test, run the monitor directly on CachyOS alongside Unsloth. Do not make remote hardware monitoring or network exposure a first-release requirement.

Keep one shared application and repository. Do not create separate Fedora and CachyOS editions.

The listed hardware is test hardware, not a requirement for other users. Discover actual devices instead of hardcoding names, capacities, or paths.

3. MANUAL LAUNCH — NO AUTOSTART

The application must start only when the user opens it.

Do not:
- Add an autostart option.
- Register boot or login startup entries.
- Install a background service.
- Create scheduled startup tasks.
- Automatically launch the application during installation.

Users can configure startup themselves through their operating system. Brief optional documentation is acceptable, but the application must not manage startup.

Once opened, the monitor should automatically detect Unsloth, refresh readings, and reconnect when needed.

Closing the main window must exit the application and stop its collectors by default.

An explicit “Minimize to tray” action is acceptable. Do not silently keep the application running after the user closes its window. Handle desktops without a system tray gracefully.

Prevent accidental duplicate instances.

4. PLATFORM STRATEGY

LINUX FIRST

Prioritize:
- CachyOS and Arch Linux.
- Fedora.
- Ubuntu and Debian.
- Common derivatives and other compatible distributions.

Support Wayland and X11 where practical.

Start with x86_64. Do not advertise other architectures without building and testing them.

Clearly distinguish:
- Tested distributions and versions.
- Expected but untested compatibility.
- Known limitations.
- Unsupported configurations.

A successful Fedora test does not establish CachyOS compatibility, and successful tests on two distributions do not establish universal Linux support.

WINDOWS AFTERWARD

After the Linux version is working reliably, implement Windows support, initially targeting Windows 11.

Reuse the shared interface and Unsloth integration. Keep platform-specific hardware collectors and desktop integration separate.

Do not delay the first useful Linux version by implementing both operating systems simultaneously.

5. DASHBOARD DESIGN

Use this arrangement as the visual reference:

┌──────────────────────────────────────────────────────────┐
│ UNSLOTH AI SERVER                              ● ONLINE  │
├───────────────────────────┬──────────────────────────────┤
│ MODEL                     │ INFERENCE                    │
│ Qwen3.8-27B Q4_K_XL       │ ● GENERATING                │
│ Context: 128K             │ 21.4 tok/s                   │
│ Backend: ROCm             │ 8,421 tokens                 │
├───────────────────────────┴──────────────────────────────┤
│ RX 9060 XT 16GB                                          │
│ GPU       ███████████████████░  94%                     │
│ VRAM      ████████████████░░░  13.8 / 16 GB             │
│ Temp      64°C          Power  137 W                     │
├──────────────────────────────────────────────────────────┤
│ Ryzen 5 5600X       RAM              SYSTEM              │
│ 32% / 57°C          11.2 / 16 GB     Uptime  06:42:18   │
└──────────────────────────────────────────────────────────┘

All names, readings, context values, speeds, and backend labels in this example are illustrative. They are not confirmed configuration or measurements.

Create a proper graphical application inspired by this arrangement, not an ASCII-rendering application.

Visual style:
- Dark, clean, industrial, and server-like.
- Charcoal backgrounds.
- Readable text and restrained accent colors.
- Thin borders and minimal corner rounding.
- Compact spacing without making the interface cramped.
- Clear progress bars.
- Small optional rolling graphs.

Avoid blur, glow, excessive gradients, animated backgrounds, and unnecessary transitions.

Make the window resizable and suitable for leaving open on a secondary display.

Handle display scaling and smaller window sizes without overlapping controls.

Communicate status through text as well as color.

6. INFORMATION TO DISPLAY

HARDWARE

GPU name.
GPU utilization.
Dedicated VRAM used and total.
GPU temperature.
GPU power draw.
CPU name and utilization.
CPU temperature when accessible.
System RAM used and total.
System uptime.

UNSLOTH

Connection status.
Actual loaded model when identifiable.
Quantization when identifiable.
Configured context limit when exposed.
Actual inference backend when verified.
Idle or generating state when reliably exposed.
Output tokens per second when reliably obtainable.
Generated output-token count when reliably obtainable.
Request duration when reliably obtainable.

OPTIONAL LATER ADDITIONS

Swap usage.
Disk and network activity.
GPU fan speed.
Multiple-GPU views.
Additional GPU vendors.

An unsupported GPU or missing sensor must not prevent the rest of the application from working.

7. VERIFY UNSLOTH CAPABILITIES

Earlier discussion suggested that Unsloth might expose health, model, and inference-status information. These capabilities have not been verified against my installed version.

Do not assume:
- Particular endpoints exist.
- An OpenAI-compatible API exposes internal server telemetry.
- A status endpoint provides live token counts or generation speed.
- A model list proves which model is currently loaded.
- Configured context and current context usage are both available.

Inspect matching official documentation or source code and, where possible, actual responses from the installed version.

Classify each measurement as:
1. Available from the operating system.
2. Available from a verified Unsloth interface.
3. Available from reliable existing telemetry or logs.
4. Unavailable or not exposed.

Display “—”, “Unknown”, “Not exposed”, or another accurate state when a value is unavailable.

Never invent values, substitute plausible numbers, or silently show demonstration data.

Do not claim that integration with the CachyOS installation works until it has actually been validated.

Missing Unsloth telemetry must not block development of the hardware dashboard.

8. PASSIVE MONITORING AND ACCURACY

The application must work alongside existing Unsloth usage, including requests from other applications.

Users must not need to chat through this monitor.

Prefer verified read-only interfaces and, where appropriate, existing logs.

Do not silently:
- Introduce a proxy.
- Intercept traffic.
- Patch Unsloth.
- Change client API endpoints.
- Start or stop Unsloth.
- Modify inference settings.
- Expose the service to the network.

Do not generate prompts, run benchmarks, or load models merely to collect statistics.

If some inference measurements are not passively available, explain the limitation and leave those fields unavailable.

Any integration requiring changes to Unsloth or client configuration must be a separately explained optional feature.

ACCURACY RULES

Distinguish machine-wide readings from Unsloth-specific measurements.

GPU activity does not establish that Unsloth is generating.

An AMD GPU does not establish that the inference backend is ROCm.

Do not infer context usage from VRAM consumption.

Keep configured context limits, current context usage, output limits, and generated output counts separate.

Keep current-request statistics separate from last-completed-request statistics and lifetime totals.

Calculate tokens per second only from trustworthy token counts and timing.

Do not count words, characters, or streamed chunks as tokens.

Label whole-request throughput differently from generation-only throughput.

Use accurate units and labels. Do not label a GPU power reading as whole-computer power consumption.

Track source, timestamp, unit, and availability internally for each metric.

If remote endpoint configuration is later supported, clearly label which computer provides the hardware readings.

9. CONNECTION AND LIFECYCLE BEHAVIOR

When the application opens:
Collect an initial hardware snapshot.
Check whether Unsloth is reachable.
Populate only verified Unsloth fields.

When Unsloth is offline:
Show UNSLOTH OFFLINE.
Continue hardware monitoring.
Retry automatically with bounded backoff.

When Unsloth starts:
Detect it without requiring a manual reconnect.
Update supported fields.
Document the expected detection delay at the chosen polling interval.

When the model changes:
Update from reliable information.

When generation starts or stops:
Update only when the state is reliably observable.

When Unsloth stops, crashes, or restarts:
Remain responsive.
Reconnect automatically.
Clear or mark stale readings.

Distinguish offline, authentication required, unsupported response, and online with no model loaded when evidence allows.

An unreachable endpoint does not automatically prove that Unsloth crashed.

10. LOW RESOURCE USAGE — CORE REQUIREMENT

The application runs on computers used for AI hosting. CPU time, system RAM, GPU resources, and memory bandwidth must remain available for inference.

Do not promise zero overhead. Measure it.

INITIAL ENGINEERING TARGETS

Aim for:
- No more than 100 MiB steady-state resident memory.
- Investigation and justification for sustained usage above 150 MiB.
- Average CPU usage below 0.5% of one logical CPU during normal visible operation at the default refresh interval.
- Lower CPU usage when minimized.
- Bounded memory consumption over long sessions.
- No sustained background disk writes.

These are targets, not claims that the implementation already meets them.

Include helper processes in measurements.

Distinguish CPU usage relative to one logical CPU from usage relative to the entire computer.

Measure startup separately from steady-state operation.

Validate the packaged release on the CachyOS test machine. Preliminary Fedora measurements are useful but not a substitute.

11. TECHNOLOGY AND ARCHITECTURE

Python 3 with PySide6/Qt is the initial implementation candidate, not a mandatory choice.

Build a small functional prototype and measure its overhead before committing to a large implementation.

Keep this stack if it meets the requirements. If it does not, first investigate simple optimizations, then propose a lighter native alternative with evidence and trade-offs.

Prefer a simple widget-based interface and inexpensive rendering.

Do not use Electron, an embedded browser, a separate application web server, or a full observability stack.

The installed application must not require containers.

Do not import or bundle machine-learning frameworks, load models, or initialize an inference runtime for monitoring.

Do not create CUDA, ROCm, or other GPU compute workloads.

Ordinary window rendering and desktop compositing are separate from compute. Do not promise literally zero graphics-memory usage.

Separate:
- UI.
- Shared metric definitions and application state.
- Linux hardware collectors.
- Future Windows hardware collectors.
- Unsloth integration.
- Settings and desktop integration.

Keep OS-specific details out of the shared UI.

Use explicit states for unavailable, stale, unsupported, and permission-denied readings.

Discover devices and sensors rather than assuming the relevant Linux GPU is card0.

Missing files, sensors, optional utilities, or permissions must not crash the application.

Keep potentially blocking collection and network requests off the GUI thread.

12. EFFICIENT POLLING AND RENDERING

Use approximately five seconds as the default refresh interval.

Collect an initial snapshot immediately without blocking the UI. Where a measurement needs a baseline interval, show an honest pending state until it is available.

Offer faster refresh as an optional setting with an overhead warning.

Cache static information such as hardware names and total memory.

Do not rediscover devices or request unchanged model metadata on every update.

Avoid repeatedly launching external commands or heavyweight helpers.

Do not repeatedly scan entire logs, process trees, or filesystem directories.

Use bounded background work. Slow responses must not cause queued tasks, threads, or pending requests to accumulate.

Reuse connections where appropriate and apply bounded timeouts.

Keep an unresponsive Unsloth request from blocking hardware monitoring.

Check whether optional GPU queries unnecessarily wake an idle GPU or increase idle power. Reduce polling or disable problematic optional measurements when necessary.

WHEN MINIMIZED OR EXPLICITLY HIDDEN TO THE TRAY

Stop graph rendering and unnecessary UI updates.
Reduce polling, for example to every 15–30 seconds.
Refresh promptly when visible again.
Do not maintain invisible animations.

HISTORY AND LOGGING

Update only changed interface elements.
Keep graphs optional and their history short and fixed in size.
Do not persist every sample.
Persistent historical monitoring is outside the first version.
Use bounded, rotated diagnostic logs.
Do not log normal readings on every refresh.

13. SAFETY AND CONFIGURATION

Run as a normal user.

Do not change:
- Fan curves.
- GPU settings.
- Power limits.
- Kernel modules.
- BIOS settings.
- Existing AI configuration.

Do not run sensor-detection procedures that modify the system.

Do not silently install drivers, privileged services, or system dependencies.

Provide editable connection settings.

Handle authentication securely when required.

Never log credentials, prompt content, or completions.

Do not request that I paste secrets into the chat or commit them to GitHub.

Store preferences in appropriate user configuration directories.

Use an isolated development environment and reproducible dependencies. Do not use sudo pip or overwrite unrelated configuration.

14. EASY LINUX INSTALLATION

End users should not need to install Python, activate an environment, run pip, or compile the application.

Provide a straightforward downloadable Linux package.

Evaluate AppImage as the first portable release format. Verify its suitability instead of claiming universal compatibility.

Choose and document a build baseline appropriate for the target distributions.

Bundle the required runtime where appropriate while avoiding unnecessary dependencies.

Test the actual packaged application, including:
- Qt plugins.
- Icons and fonts.
- Networking.
- Sensor access.
- Wayland and X11 where environments are available.

Document unavoidable host dependencies, executable-permission steps, and limitations.

Consider Flatpak or distribution-specific packages later where useful. Verify sandbox permissions before promising hardware telemetry.

Prefer one well-tested primary format over several poorly tested formats.

Provide:
- A clear primary download.
- Simple launch instructions.
- An application icon.
- Optional user-level launcher integration.
- Clean uninstall instructions.

Launcher integration must not create autostart entries.

15. GITHUB REQUIREMENTS

Suggested repository name: unsloth-monitor.

Use my GitHub account as the project’s home.

Inspect available GitHub access, the existing Git remote, and relevant repositories before creating anything.

Do not invent my username, repository URL, authentication status, or repository state.

Use available authenticated tools to resolve details rather than asking me for information already accessible.

Before creating or publishing a repository, confirm the intended owner and public/private visibility if those decisions are unresolved.

Do not create duplicates, change visibility, overwrite unrelated work, or rewrite shared history without approval.

Required repository contents:
- Complete source code.
- Dependency and project configuration.
- README.
- Installation and usage instructions.
- Architecture and telemetry documentation.
- Compatibility and troubleshooting documentation.
- Tests.
- Packaging configuration.
- GitHub Actions workflows.
- A license confirmed before public release.
- Changelog or release notes.
- Linux-first roadmap with Windows as a later phase.
- Appropriate .gitignore.

Make meaningful commits.

Use CI for automated checks and builds where practical.

Make verified packages available through GitHub Releases when publication is authorized.

Store generated packages as workflow artifacts or release assets rather than repeatedly committing binaries to the source tree.

Never commit credentials, private configuration, model weights, inference content, or private logs.

Do not claim that a push, build, test, or release succeeded unless it actually did.

If GitHub access is unavailable, continue local work and explain the exact connection or push steps needed.

16. PERSISTENT PROJECT DOCUMENTATION

Save the consolidated requirements in PROJECT_SPEC.md.

Save essential coding-agent instructions in AGENTS.md, respecting any existing repository instructions.

Maintain a concise progress document, such as docs/PROGRESS.md, containing:
- Implemented features.
- Verified hardware and Unsloth capabilities.
- Known limitations.
- Test results.
- Measured overhead.
- Packaging and release status.
- The next concrete task.

Keep these files current so another Codex session can continue without reconstructing the project from chat history.

17. TESTING AND ACCEPTANCE

Test:
- Hardware monitoring while Unsloth is offline.
- Automatic detection when Unsloth starts.
- Reconnection after restart.
- Authentication failures.
- Unsupported or changed responses.
- Missing sensors and insufficient permissions.
- Model changes where supported.
- Correct unavailable and stale states.
- UI responsiveness during slow requests.
- Bounded polling, queues, and history.
- Long-session memory behavior.
- Clean shutdown without orphaned collectors.
- Packaged launch without the development environment.
- Absence of automatic startup registration.

Use simulated telemetry only in separate tests or an explicitly selected demo mode.

Normal operation must never silently use demonstration values.

Distinguish unit tests, CI checks, package launch tests, and real hardware validation.

A passing headless CI run does not establish GPU compatibility across distributions.

Maintain a compatibility table describing what was actually tested.

18. AI PERFORMANCE VALIDATION

Benchmarks require explicit authorization during development or testing. The installed monitor must never automatically send test prompts or run benchmarks.

Compare:
1. The monitor closed.
2. The packaged monitor open at default settings.
3. The monitor minimized where useful.

Keep the model, backend, context, prompt, generation settings, concurrency, and other relevant conditions consistent.

Use warm-up runs and repeated measurements. Account for normal run-to-run variation.

Compare:
- Generation throughput.
- Time to first token when measurable.
- Monitor CPU and memory usage.
- Relevant GPU memory and idle-power changes.

The goal is no repeatable inference regression beyond measurement noise.

Investigate a repeatable throughput reduction above approximately 1% when it can be distinguished from normal variation.

Do not present inconclusive results as proof of no impact.

Document targets separately from actual results and include test conditions.

When a feature materially increases overhead, simplify it, disable it by default, or leave it out.

19. WINDOWS PORT AFTER LINUX

Reuse the shared UI and Unsloth integration.

Implement Windows telemetry through appropriate verified interfaces.

Do not assume Linux collectors work on Windows or promise vendor-specific measurements without testing.

Provide a packaged application or installer that does not require users to install Python.

Preserve manual launch, normal-user operation, and clean shutdown.

Do not silently install drivers, privileged services, startup entries, or scheduled tasks.

Measure Windows overhead independently.

Do not advertise Windows support before a working packaged build has been tested.

20. DEVELOPMENT MILESTONES

MILESTONE 1 — FEDORA PROTOTYPE

Inspect the workspace and development environment.

Create or update project documentation and a small implementation plan.

Build a runnable native Linux dashboard that:
- Shows actual Fedora hardware readings.
- Handles unavailable sensors correctly.
- Handles an unavailable Unsloth connection correctly.
- Launches manually and exits cleanly.

Measure initial resource usage.

Do not wait for CachyOS access before starting this milestone.

MILESTONE 2 — CACHYOS VERIFICATION

Provide the smallest useful read-only diagnostic script for the separate CachyOS machine when needed.

Verify its hardware telemetry and installed Unsloth interfaces from actual results.

Run the same application on CachyOS and keep those test results separate from Fedora results.

MILESTONE 3 — VERIFIED UNSLOTH FEATURES

Add the model and inference information that verified telemetry supports.

Leave unsupported fields honestly unavailable.

Do not introduce hidden dependencies merely to fill every field in the preview.

MILESTONE 4 — LINUX PACKAGE AND RELEASE

Refine the interface without unnecessary overhead.

Build and test the Linux package.

Complete documentation, CI, compatibility records, and authorized GitHub publication.

MILESTONE 5 — EXPANSION

Improve Linux reliability and distribution coverage.

Then implement and test Windows support.

Each milestone must produce something runnable and testable. Do not postpone a working Linux version until every optional feature exists.

21. HOW TO WORK WITH ME

Edit the actual project files and run available tests when tool access permits.

Provide complete runnable code, not pseudocode or unexplained placeholders.

Do not ask me to copy many individual fragments when you can create files directly.

Proceed with non-blocked development instead of repeatedly asking permission for routine work.

Ask only for essential unresolved decisions, required access, or local test results.

Do not ask me to repeat hardware details already included here.

Do not recommend Grafana, OpenLIT, generic system monitors, or a replacement application instead of building this project.

Do not claim access to a computer, repository, display session, or GPU that you do not actually have.

Distinguish actual local access from a development sandbox.

When a task requires the separate CachyOS computer, provide concise instructions or one read-only diagnostic script. Explain what it collects and avoid secrets or inference content.

Do not make system changes, install dependencies, or send inference requests as part of the initial diagnostic.

Continue unrelated implementation while waiting for external validation.

22. BEGIN NOW

Read the full specification.

Inspect the workspace, existing repository instructions, available tools, and actual Fedora development environment using safe read-only commands.

Check existing GitHub configuration without exposing credentials.

Create or update PROJECT_SPEC.md, AGENTS.md, and the progress document.

Start the first runnable Fedora prototype with real hardware measurements, honest unavailable states, manual launch, and low overhead.

Do not stop after presenting a plan when you can implement the first milestone.

At the end of each working session, report concisely:
- What changed.
- What actually ran and passed.
- What remains unverified.
- How to launch the current build.
- The single next action needed from me, if any.

The first deliverable is a working, lightweight Linux dashboard on Fedora. The same code will then be tested alongside Unsloth on CachyOS, packaged for broader Linux use, maintained on GitHub, and later ported to Windows.
