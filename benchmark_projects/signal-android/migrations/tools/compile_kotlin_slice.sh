#!/usr/bin/env bash
set -euo pipefail

project="$1"
output="$2"
version="$3"

cache="$HOME/.gradle/caches/modules-2/files-2.1"
one_jar() {
  find "$1" -type f -name '*.jar' | sort | tail -n 1
}

compiler="$(one_jar "$cache/org.jetbrains.kotlin/kotlin-compiler-embeddable/$version")"
stdlib="$(one_jar "$cache/org.jetbrains.kotlin/kotlin-stdlib/$version")"
reflect="$(one_jar "$cache/org.jetbrains.kotlin/kotlin-reflect/$version")"
script_runtime="$(one_jar "$cache/org.jetbrains.kotlin/kotlin-script-runtime/$version")"
trove="$(one_jar "$cache/org.jetbrains.intellij.deps/trove4j/1.0.20200330")"
compiler_coroutines="$(one_jar "$cache/org.jetbrains.kotlinx/kotlinx-coroutines-core-jvm/1.10.2")"
annotations="$(one_jar "$cache/org.jetbrains/annotations/26.0.2-1")"

for dependency in "$compiler" "$stdlib" "$reflect" "$script_runtime" "$trove" "$compiler_coroutines" "$annotations"; do
  test -f "$dependency"
done

mkdir -p "$output/classes"
find "$output/classes" -type f -delete
evaluator_src="${EVALUATOR_SRC:-$project/evaluator-src}"
sources=($(find "$project/immutable-src" "$evaluator_src" "$project/stubs" -type f \( -name '*.kt' -o -name '*.java' \) | sort))
kotlin_sources=($(find "$project/immutable-src" "$evaluator_src" "$project/stubs" -type f -name '*.kt' | sort))
java_sources=($(find "$project/immutable-src" "$evaluator_src" "$project/stubs" -type f -name '*.java' | sort))

java -cp "$compiler:$stdlib:$reflect:$script_runtime:$trove:$compiler_coroutines:$annotations" \
  org.jetbrains.kotlin.cli.jvm.K2JVMCompiler \
  -no-stdlib -no-reflect -jvm-target 17 \
  -classpath "$stdlib:$compiler_coroutines:$annotations" \
  -d "$output/classes" \
  "${sources[@]}"

if test "${#java_sources[@]}" -gt 0; then
  javac --release 17 -cp "$output/classes:$stdlib:$compiler_coroutines:$annotations" -d "$output/classes" "${java_sources[@]}"
fi

test -n "$(find "$output/classes" -type f -name '*.class' -print -quit)"
jar --create --file "$output/runtime.jar" -C "$output/classes" .
printf '%s\n' "$stdlib:$compiler_coroutines:$annotations" > "$output/runtime.classpath"
