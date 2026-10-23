#!/usr/bin/env bash
set -euo pipefail

project="${1:?usage: build_android_harness.sh <project-root>}"
project="$(cd "$project" && pwd)"
tools_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sdk="${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}"
build_tools="${ANDROID_BUILD_TOOLS:-$sdk/build-tools/37.0.0}"
android_jar="$sdk/platforms/android-37.0/android.jar"
output="$project/build"
source_manifest="$project/src/main/AndroidManifest.xml"
role="$(basename "$project")"
migration="$(cd "$project/../.." 2>/dev/null && pwd || true)"

for tool in aapt2 d8 apksigner; do
  test -x "$build_tools/$tool" || { printf 'missing Android build tool: %s/%s\n' "$build_tools" "$tool" >&2; exit 69; }
done
test -f "$android_jar" || { printf 'missing Android API 37 jar: %s\n' "$android_jar" >&2; exit 69; }

evaluator_src="${EVALUATOR_SRC:-$migration/android/evaluator/$role}"
test -d "$evaluator_src" || { printf 'evaluator source unavailable: %s\n' "$evaluator_src" >&2; exit 65; }
EVALUATOR_SRC="$evaluator_src" bash "$project/tools/build.sh" "$project" "$output"
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
mkdir -p "$(dirname "$keystore")"
if [[ ! -f "$keystore" ]]; then
  keytool -genkeypair -noprompt -keystore "$keystore" -storepass android \
    -alias androiddebugkey -keypass android -dname 'CN=Android Debug,O=Benchmark,C=US' \
    -keyalg RSA -keysize 2048 -validity 10000 >/dev/null 2>&1
fi
"$build_tools/apksigner" sign --ks "$keystore" --ks-pass pass:android \
  --key-pass pass:android --out "$output/harness.apk" "$output/harness-unsigned.apk"
"$build_tools/apksigner" verify "$output/harness.apk"
