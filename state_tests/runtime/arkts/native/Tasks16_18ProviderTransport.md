# Task18 Provider Metadata Transport

Evaluator-only, read-only system metadata observation. Does not replace any
production picker, store, copier, presenter or business operation. Native `bm`
failure (including current user -2) remains in the raw native checkpoints; the
host uses separately authorized HDC access, not application permission changes.

## Protocol

1. Native UI captures before/after `aa dump -e`, the actual mounted page receiver,
   exact monitored AbilityContext, UIExtension ancestry anchors and one pending
   original `AudioViewPicker.select` call. Exactly one new active provider record
   must match the exact root host bundle/module/ability. No guessed provider name.
2. If the in-process metadata read cannot establish identity, and the build and
   invocation explicitly enable host transport, emit one
   `ARKTS_16_18_PROVIDER_REQUEST <JSON>` hilog marker. It binds the execution nonce,
   canonical task/case, candidate, inventory user, exact provider identity,
   record ID/PID, host scope, SDK call ID/start, and request timestamp. Protocol
   v2 also binds actual `getAppContext().getApplicationContext()` application
   name/cacheDir and both the native and host response paths. The original
   Context is used directly; no reconstructed or cloned Context is passed.
3. Independent worker matches the fresh nonce and checks marker PID against the
   live candidate `pidof`. It reads only `bm dump -n <observed-provider> -u <user>`
   through HDC. The original stdout, stderr, exit status, UTF-8 bytes/SHA-256,
   host command timestamps, serial, role and marker PID are retained.
4. Response uses the official debug-bundle interface, locked to this exact
   candidate: `hdc file send -b <bundle> <local> data/storage/el2/base/cache/Tasks16_18_provider_<nonce>.json.tmp`.
   The remote path is relative, with no leading slash. There is no ordinary
   protected-host-path write, root, policy adjustment, host chmod or host mv.
   Native reads its actual `ApplicationContext.cacheDir/...json.tmp` using SDK
   `fs.statSync` and bounded `fs.readTextSync`, computes the raw stdout digest with SDK
   crypto, validates the entire echoed request, then calls `fs.renameSync` on its
   own cache file and reads the final file back exactly. A partial JSON or
   changing byte length is retried within the same existing observation budget.
   No precreated ready file or speculative mkdir is used.
   Host then uses `file recv -b <bundle>` on the final relative path and compares
   all received bytes to its original response. Only this receipt permits
   `delivered`. All send/recv stdout/stderr are retained; exit zero alone is never
   success. `FileTransfer finish` must name one file and the exact byte count.
5. Identity still requires installed metadata declaring this exact provider as
   a system app with the enabled/visible exact extension and literal
   `extensionTypeName: sysPicker/audioPicker`. No numeric type inference.
   All previous actual GIVEN, same-page, preferences, native call and UI ancestry
   assertions remain required. Missing or inconsistent evidence stays unscored.

## Bounds And Clocks

- Worker discovery: at most 60 seconds / 120 reads, sleeping 500 ms between reads;
  no repeated polling-log files. Exactly one request is served.
- Native response wait: at most 8 seconds / 16 reads with 250 ms delays, within
  the existing whole-probe budget. Raw/partial checkpoints publish before awaits.
- File-not-found (13900002), partial JSON and changing transfer lengths are
  retried; permission and other filesystem errors stop with their real code/message.
  The response is bounded to 3 MiB
  and its UTF-8 byte length must agree with the real native file stat.
- HDC metadata command: 3-second timeout; transfer steps: 2 seconds each.
- Final-file receipt: at most 8 reads with 250 ms delays, retaining every command
  and failed receipt. Worker shutdown still makes one final receipt attempt so
  completion cannot race the native rename.
- Native and host clocks are never directly compared. The unique request and
  response are causally inside native snapshots of the same pending SDK call;
  timestamps are ordered only within their own clock domain.
- Executor joins/stops the worker, then removes only the two exact nonce files,
  through exact-bundle `shell -b ... rm`, including failure paths. Owned-app
  uninstall also removes this app cache.
  Local audit evidence is retained; no directory ownership or policy is changed.

## Audit And Integration

`arkts_native_device.cjs` adds `supportsTasks16To18ProviderHost` and the worker
source hash only for task18's `ns_state_003_message_picker_launch` with
`--fixture bundle --native-ui`. No extra user flag is needed. Executor passes
`-s ltbProviderHostBridge 1`, the fresh execution nonce and inventory user.

Execution evidence includes worker source hash, configuration, matched request
log/hash, live PID output, actual Context/cache path mapping, command audit, original response/hash and worker
report. `apply_arkts_device_evidence.py` calls the worker's pure local
`--verify-evidence` mode: it checks source/invocation/cleanup and artifact binding,
recomputes raw pending-provider identity, and rejects unsupported or altered
evidence instead of trusting `verified` booleans. Old runs are not backfilled.

Build with the existing signing arguments and a fresh output directory:

```sh
node scripts/runtime_semantics/arkts_native_device.cjs \
  --source final_dev_nodes/18_custom_notification_sounds_final_26_06_1 \
  --task 18_custom_notification_sounds --fixture bundle --role final \
  --case ns_state_003_message_picker_launch --native-ui \
  --output-dir experiment_results/runtime_transition_20261019/device-calibration/task18-provider-host-cache
```

Then use the existing `arkts_device_execute.cjs BUILD_REPORT SERIAL` command.
The parent owns signing/build/device execution. Local SDK-declaration and mock
boundary tests are not claimed as device passes. Prior `/data/local/tmp` +
delegator `cat` and ordinary host-cache writes failed; their NS rows are unchanged.
The directory existed: HDC send explicitly reported permission denied despite
exit zero. Official `-b` send with the documented relative path was independently
smoke-tested by the parent, but host mv remained denied. The native rename path
is now device-verified in
`experiment_results/runtime_transition_20261019/device-calibration/task18-picker-linked-provenance`
and its independent fresh-install `-repeat` execution. Both canonical rows
PASS after actual original-page call provenance is linked, with separately
verified host receipts and cleanup. No native pass was inferred from the smoke.

Official path and access prerequisites: [OpenHarmony HDC documentation](https://github.com/openharmony/docs/blob/master/zh-cn/application-dev/dfx/hdc.md).
`-b` requires a started application signed with a debug certificate; buildMode
alone does not prove eligibility. Local HDC 3.2.0c help advertises send/recv -b.
Unsupported access stays NS without fallback to privilege changes.
