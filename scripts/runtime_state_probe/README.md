# Runtime State Probe

Evaluator-side feasibility tools tested on 2026-09-08. These are not a completed
benchmark harness. No LLM, application setter, or application method evaluation
is used by these collectors. Existing fixture panels and case-result markers
must not be used as evidence.

## Android

Requires a debuggable APK, ADB, and JDK 21. Open the real application Activity.
Use the current app PID, not a previous session's PID.

```powershell
javac --add-modules jdk.jdi RuntimeStateProbe.java
adb -s emulator-5554 forward tcp:18700 jdwp:<PID>
java --add-modules jdk.jdi -cp . RuntimeStateProbe 18700 snapshot 'io\.element\..*QrCodeIntroState'
java --add-modules jdk.jdi -cp . RuntimeStateProbe 18700 watch 'androidx\.compose\.runtime\.SnapshotMutableStateImpl\$StateStateRecord' value 30
adb -s emulator-5554 forward --remove tcp:18700
```

Snapshots suspend the VM. Watchpoints suspend the writing thread, and broad
Compose watches have substantial overhead. Do not use them to judge deadlines.
Loaded-class enumeration misses future classes; instance enumeration is capped
at 30 per class. Old state objects can remain alive. An object existing in the
heap does NOT establish that the current UI consumes it. No Rust heap support
or Compose active-snapshot resolution has been implemented.

## ArkTS

Tested on API 23 / HarmonyOS 6.1.0.115 / DevEco 26.0.0.821, debuggable HAPs.
The protocol is implementation-specific, not asserted to be a stable public API.

```powershell
hdc -t 127.0.0.1:5557 shell aa start -D -b <BUNDLE> -a EntryAbility
hdc -t 127.0.0.1:5557 shell pidof <BUNDLE>
hdc -t 127.0.0.1:5557 fport tcp:18712 ark:<PID>@<PID>@Debugger
node ark_runtime_probe.mjs ws://127.0.0.1:18712 debug start.jsonl 20
# After startup has resumed and the app is rendered:
hdc -t 127.0.0.1:5557 fport tcp:18713 ark:<PID>@<BUNDLE>
node ark_runtime_probe.mjs ws://127.0.0.1:18713 state states.jsonl 60
# Operate real UI from another shell while the collector is running.
```

State mode receives property values, decorator, owning component, dependency
element IDs, window ID and runtime timestamps. Values may be shallow strings
such as `[object Object]`. No initial complete-state snapshot, event-loss bound,
or timing overhead guarantee was established in this pilot.

`inspect` mode on a fresh debugger forward pauses on JS activity and reads
scope/this properties. It follows selected known field names and Proxy targets
to depth 8, without invoking getters. This demonstrates nested-value access;
it does NOT solve automatic semantic binding for arbitrarily refactored agents.
Use throwaway test accounts: raw debugger properties can contain private data.
Do not publish raw traces from real user sessions.

The bundled `ws` package is required; override its path with `PROBE_WS_MODULE`.
The built-in Node WebSocket client failed this runtime's handshake. Create a
fresh HDC forward after failed connections. Stop collectors before cleanup.
Remove only the forwards created for this run; never use remove-all.

## Evidence Replay

```powershell
node summarize_probe.mjs C:\Users\xiexi\qingyu\verification_reports\runtime_state_probe_20260908
```

This deterministically checks captured evidence, not a running application.
Its OBSERVED checks are capability/partial-state checks, not testcase passes.
Preserve both original JSONL/TSV and the generated probe-summary.json.
