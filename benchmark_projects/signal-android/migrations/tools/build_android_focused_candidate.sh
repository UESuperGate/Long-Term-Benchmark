#!/usr/bin/env bash
set -euo pipefail

project="${1:?usage: build_android_focused_candidate.sh <candidate-project> <migration-root>}"
migration="${2:?usage: build_android_focused_candidate.sh <candidate-project> <migration-root>}"
project="$(cd "$project" && pwd)"
migration="$(cd "$migration" && pwd)"
tools_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sdk="${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}"
build_tools="${ANDROID_BUILD_TOOLS:-$sdk/build-tools/37.0.0}"
android_jar="$sdk/platforms/android-37.0/android.jar"
output="$project/build"
source_manifest="$project/src/main/AndroidManifest.xml"

for tool in aapt2 d8 apksigner; do
  test -x "$build_tools/$tool" || { printf 'missing Android build tool: %s/%s\n' "$build_tools" "$tool" >&2; exit 69; }
done
test -f "$android_jar" || { printf 'missing Android API 37 jar: %s\n' "$android_jar" >&2; exit 69; }
test -x "$project/tools/build.sh" || { printf 'candidate build script unavailable: %s\n' "$project/tools/build.sh" >&2; exit 65; }
test -f "$migration/android/evaluator/probe-candidates.tsv" || { printf 'probe candidate inventory unavailable\n' >&2; exit 65; }

rm -rf "$output"
mkdir -p "$output"
selected_name=''
selected_main=''
selected_source=''
while IFS=$'\t' read -r name main source; do
  [[ -n "$name" && "${name:0:1}" != '#' ]] || continue
  candidate_source="$migration/android/evaluator/$source"
  test -d "$candidate_source" || continue
  rm -rf "$output"
  mkdir -p "$output"
  if EVALUATOR_SRC="$candidate_source" COMPILE_KOTLIN_SLICE="$tools_root/compile_kotlin_slice.sh" \
      bash "$project/tools/build.sh" "$project" "$output" >"$output.compile.log" 2>&1; then
    selected_name="$name"
    selected_main="$main"
    selected_source="$source"
    break
  fi
  cp "$output.compile.log" "/tmp/${USER:-user}-${name}-focused-compile.log"
done < "$migration/android/evaluator/probe-candidates.tsv"

if [[ -z "$selected_name" ]]; then
  printf 'no evaluator probe was compile-compatible with candidate: %s\n' "$project" >&2
  exit 1
fi

classpath="$(cat "$output/runtime.classpath")"
mkdir -p "$output/harness-classes" "$output/dex"
package_name="$(sed -n 's/.*package="\([^"]*\)".*/\1/p' "$source_manifest" | head -n 1)"
test -n "$package_name" || { printf 'manifest package unavailable: %s\n' "$source_manifest" >&2; exit 65; }

printf '%s\n' \
  '<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="'"$package_name"'">' \
  '  <application android:debuggable="true" android:label="Benchmark evaluator">' \
  '    <activity android:name="evaluator.harness.HarnessActivity" android:exported="true" />' \
  '  </application>' \
  '</manifest>' > "$output/harness-manifest.xml"

javac --release 17 -cp "$android_jar:$output/runtime.jar" \
  -d "$output/harness-classes" \
  "$tools_root/android-harness/evaluator/harness/HarnessActivity.java"
jar --create --file "$output/harness.jar" -C "$output/harness-classes" .

"$build_tools/aapt2" link \
  -o "$output/harness-unsigned.apk" \
  --manifest "$output/harness-manifest.xml" \
  -I "$android_jar" \
  --min-sdk-version 23 \
  --target-sdk-version 37 \
  --version-code 1 \
  --version-name evaluator

IFS=':' read -r -a dependencies <<< "$classpath"
"$build_tools/d8" --release --min-api 23 --lib "$android_jar" \
  --output "$output/dex" \
  "$output/runtime.jar" "$output/harness.jar" "${dependencies[@]}"
zip -q -j "$output/harness-unsigned.apk" "$output/dex/classes.dex"

keystore="$tools_root/.android-harness/debug.keystore"
test -f "$keystore" || { printf 'shared evaluator keystore unavailable: %s\n' "$keystore" >&2; exit 69; }
"$build_tools/apksigner" sign --ks "$keystore" --ks-pass pass:android \
  --key-pass pass:android --out "$output/harness.apk" "$output/harness-unsigned.apk"
"$build_tools/apksigner" verify "$output/harness.apk"

node -e 'const fs=require("fs"); const out=process.argv[1]; const data={schemaVersion:1,probeCandidate:process.argv[2],probeMainClass:process.argv[3],probeSource:process.argv[4],packageName:process.argv[5]}; fs.writeFileSync(out, JSON.stringify(data,null,2)+"\n")' \
  "$output/harness-config.json" "$selected_name" "$selected_main" "$selected_source" "$package_name"
printf 'selected probe: %s (%s)\n' "$selected_name" "$selected_main"
