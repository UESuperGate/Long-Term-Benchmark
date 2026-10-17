#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CRATE="$ROOT/elementx_harmony_full/native/matrix-sdk-bridge"
PROJECT="$ROOT/elementx_harmony_full"
MATRIX_SDK_SOURCE="$ROOT/_worktrees/matrix-rust-sdk-2214aded"
MATRIX_SDK_COMMIT="2214aded9d173c75683943e05c0aee52363ee852"
SDK_ROOT="${OHOS_SDK_ROOT:-$HOME/Library/OpenHarmony/Sdk/23}"
TARGET="aarch64-unknown-linux-ohos"
LINKER="$SDK_ROOT/native/llvm/bin/aarch64-unknown-linux-ohos-clang"
HVIGOR="${HVIGOR:-/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw}"
FEATURES="${MATRIX_BRIDGE_FEATURES:-matrix-sdk}"
FEATURE_ARGS=()

if [[ -n "$FEATURES" ]]; then
  FEATURE_ARGS=(--features "$FEATURES")
fi

if [[ ! -x "$LINKER" ]]; then
  echo "OpenHarmony linker not found: $LINKER" >&2
  exit 2
fi

ACTUAL_MATRIX_SDK_COMMIT="$(git -C "$MATRIX_SDK_SOURCE" rev-parse HEAD)"
if [[ "$ACTUAL_MATRIX_SDK_COMMIT" != "$MATRIX_SDK_COMMIT" ]]; then
  echo "Unexpected Matrix Rust SDK commit: $ACTUAL_MATRIX_SDK_COMMIT" >&2
  echo "Expected: $MATRIX_SDK_COMMIT" >&2
  exit 3
fi

source "$HOME/.cargo/env"
rustup target add "$TARGET"
export PATH="$SDK_ROOT/native/build-tools/cmake/bin:$PATH"
export CMAKE="$SDK_ROOT/native/build-tools/cmake/bin/cmake"
export CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-1}"
export CARGO_INCREMENTAL=0
export CARGO_TARGET_AARCH64_UNKNOWN_LINUX_OHOS_LINKER="$LINKER"
export CARGO_TARGET_AARCH64_UNKNOWN_LINUX_OHOS_RUSTFLAGS="-Cembed-bitcode=no -Clto=off"
export CC_aarch64_unknown_linux_ohos="$SDK_ROOT/native/llvm/bin/aarch64-unknown-linux-ohos-clang"
export CXX_aarch64_unknown_linux_ohos="$SDK_ROOT/native/llvm/bin/aarch64-unknown-linux-ohos-clang++"
export AR_aarch64_unknown_linux_ohos="$SDK_ROOT/native/llvm/bin/llvm-ar"
export RANLIB_aarch64_unknown_linux_ohos="$SDK_ROOT/native/llvm/bin/llvm-ranlib"

# Keep host and OHOS artifacts separate in time: the SDK build is large.
cargo clean --manifest-path "$CRATE/Cargo.toml"
cargo test --release --manifest-path "$CRATE/Cargo.toml" "${FEATURE_ARGS[@]}"

cargo clean --manifest-path "$CRATE/Cargo.toml"
cargo build --manifest-path "$CRATE/Cargo.toml" --target "$TARGET" --release "${FEATURE_ARGS[@]}"

OUTPUT="$CRATE/target/$TARGET/release/libelementx_matrix_sdk_bridge.a"
if [[ ! -f "$OUTPUT" ]]; then
  echo "Expected static library not produced: $OUTPUT" >&2
  exit 4
fi

if [[ ! -x "$HVIGOR" ]]; then
  echo "Hvigor wrapper not found: $HVIGOR" >&2
  exit 5
fi

(
  cd "$PROJECT"
  "$HVIGOR" --no-daemon clean --mode module -p module=entry@default
  "$HVIGOR" --no-daemon assembleHap --mode module -p module=entry@default -p product=default -p buildMode=debug
)

HAP="$PROJECT/entry/build/default/outputs/default/entry-default-unsigned.hap"
if [[ ! -f "$HAP" ]]; then
  echo "Expected HAP not produced: $HAP" >&2
  exit 6
fi

NATIVE_SO="$PROJECT/entry/build/default/intermediates/cmake/default/obj/arm64-v8a/libmatrix_native.so"
LLVM_NM="$SDK_ROOT/native/llvm/bin/llvm-nm"
if [[ ! -f "$NATIVE_SO" ]]; then
  echo "Expected native library not produced: $NATIVE_SO" >&2
  exit 7
fi

if ! "$LLVM_NM" "$NATIVE_SO" | awk '
  / elementx_matrix_bridge_abi_version$/ { abi = 1 }
  / elementx_matrix_bridge_sdk_linked$/ { linked = 1 }
  / elementx_matrix_bridge_runtime_ready$/ { runtime = 1 }
  / elementx_matrix_bridge_status$/ { status = 1 }
  / elementx_matrix_bridge_sdk_version$/ { version = 1 }
  / elementx_matrix_bridge_error_message$/ { message = 1 }
  / elementx_matrix_bridge_create_client$/ { create_client = 1 }
  / elementx_matrix_bridge_restore_client$/ { restore_client = 1 }
  / elementx_matrix_bridge_release_client$/ { release_client = 1 }
  / elementx_matrix_bridge_get_client_status$/ { client_status = 1 }
  / elementx_matrix_bridge_sync_rooms$/ { sync_rooms = 1 }
  / elementx_matrix_bridge_load_timeline$/ { load_timeline = 1 }
  / elementx_matrix_bridge_send_text$/ { send_text = 1 }
  / elementx_matrix_bridge_free_string$/ { free_string = 1 }
  END {
    exit !(abi && linked && runtime && status && version && message &&
      create_client && restore_client && release_client && client_status && sync_rooms &&
      load_timeline && send_text && free_string)
  }
'; then
  echo "Native library is missing one or more Rust ABI symbols" >&2
  exit 8
fi

if [[ "$FEATURES" == *matrix-sdk* ]]; then
  if ! "$LLVM_NM" -C "$NATIVE_SO" | awk '
    /matrix_sdk::client::Client/ { matrix_client = 1 }
    /tokio::runtime/ { tokio_runtime = 1 }
    END { exit !(matrix_client && tokio_runtime) }
  '; then
    echo "Native library does not contain Matrix SDK Client and Tokio runtime symbols" >&2
    exit 9
  fi
  if ! strings "$NATIVE_SO" | grep -F 'matrix_client_runtime_ready' >/dev/null; then
    echo "Native library does not report the verified Matrix client runtime status" >&2
    exit 10
  fi
fi

HAP_CONTENTS="$(unzip -Z1 "$HAP")"
if ! grep -Fxq 'libs/arm64-v8a/libmatrix_native.so' <<<"$HAP_CONTENTS"; then
  echo "HAP does not contain libs/arm64-v8a/libmatrix_native.so: $HAP" >&2
  exit 11
fi

echo "Rust archive: $OUTPUT"
echo "Verified HAP: $HAP"
