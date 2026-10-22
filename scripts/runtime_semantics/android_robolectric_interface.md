# Shared Runner Interface

Call android_robolectric_dependencies.prepare(config, work) while holding the
existing Android build lock. The same function is re-exported by
android_robolectric.py.

The function reuses 08_threads/.dependencies and its Maven POM unless
robolectricFoundation names another adapter. The dependencies field accepts the
existing [group, artifact, version] entries (AAR type detected from cache), or an
explicit fourth jar/aar field. Resolution uses an isolated generated POM.
Set offlineDependencies to true for cache-only resolution. excludeCommonSources
extends the default shim exclusions when the candidate's real annotation/scope
definitions are included in its source closure.

Consume these returned fields:

- jars: complete classpath including the compiled evidence/launcher bridge.
  Replace the desktop foundation classpath rather than mixing Compose versions.
- compiler, plugin, compilerArgs: Kotlin 2.2.10, real Compose plugin, and
  real Parcelize plugin.
- compileOnlyJars: prepend to the Kotlin compile classpath only. The compile SDK
  prevents instrumented Android methods from appearing as source requirements;
  Robolectric's instrumented SDK remains the runtime implementation.
- excludedCommonSources: omit Android Parcelable/Parcelize and Inject/Timber
  shims. The real dependencies provide these types.
- jvmArgs, mainClass: required JVM options and launcher. Do not invoke
  HarnessKt directly: Robolectric leaves a non-daemon SDK executor after tests.
- executionEnvironment, framework, scope: runtime labels only.
- evaluatorSources, dependencyPom: input provenance to merge into the report.

Tests use @RunWith(runtime.foundation.EvidenceRobolectricRunner::class) and
@Config(sdk = [36], manifest = Config.NONE).

RuntimeEnvironment.getApplication() provides the real Android Context. Real
AndroidX DataStore preferences 1.1.7 is in the foundation. The evidence bridge
shares only runtime.Evidence with the parent loader; candidate production and
Android classes execute in the Robolectric sandbox.

Validated infrastructure checks (not canonical benchmark scores):

- Real Android Spannable text and spans.
- Immutable production StableCharSequence under a real Compose Recomposer,
  including before/after evidence visible to the shared host harness.
- Context-backed DataStore string-set persistence across two independent store
  instances, with scopes closed between instances.

Source closure and UI resources:

- android_robolectric_sources.py --source REPO --ref REF --config CONFIG reads
  config.entrypoints and writes an explicit sources manifest. It never edits
  production Kotlin. composer_foundation.json is the current 301-file example.
- android_robolectric_resources.compile_resources builds actual candidate XML
  and drawable resources using aapt2, plus generated R and variant BuildConfig.
  Tests using those resources omit manifest = Config.NONE.
- boms accepts [group, artifact, version] entries, for example the candidate's
  androidx.compose:compose-bom:2025.07.00. alignedGroups can align cached members
  of a version-pinned family such as androidx.lifecycle:2.9.2. These options
  affect external dependency resolution only, never candidate business logic.
- The shared runner's android_ui_resources.compile_ui_resources packages real
  AAR and candidate resources. android_robolectric_ui_resources.py is the
  standalone rendered-harness counterpart maintained by the UI adapter owner.
  The real UI example is
  state_tests/runtime/android/11_room_upgrade_navigation/rendered/RoomBeginningRenderedTest.kt.
  Merely selecting this packaging path does not establish UI coverage.

Cache maintenance:

- android_robolectric_cache.py defaults to a dry run. --apply holds the shared
  build lock and removes only unreferenced, byte-identical classes.jar copies
  beside their original AARs. Referenced dependencies and original cache files
  are retained. Dependency artifacts stay under ignored .dependencies.
