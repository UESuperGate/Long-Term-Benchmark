cmake_minimum_required(VERSION 3.5.0)
project(elementx_matrix_native LANGUAGES CXX)

set(ELEMENTX_MATRIX_BRIDGE_ROOT
    "${CMAKE_CURRENT_LIST_DIR}/../../../../native/matrix-sdk-bridge"
    CACHE PATH "Path to the Element X Matrix Rust bridge crate")
set(ELEMENTX_MATRIX_BRIDGE_ARCHIVE
    "${ELEMENTX_MATRIX_BRIDGE_ROOT}/target/aarch64-unknown-linux-ohos/release/libelementx_matrix_sdk_bridge.a"
    CACHE FILEPATH "Path to the prebuilt OpenHarmony ARM64 Rust bridge archive")

if(NOT EXISTS "${ELEMENTX_MATRIX_BRIDGE_ARCHIVE}")
    message(FATAL_ERROR
        "Rust Matrix bridge archive is missing: ${ELEMENTX_MATRIX_BRIDGE_ARCHIVE}. "
        "Run scripts/build_matrix_bridge_macos.sh before invoking Hvigor.")
endif()

add_library(elementx_matrix_sdk_bridge STATIC IMPORTED GLOBAL)
set_target_properties(elementx_matrix_sdk_bridge PROPERTIES
    IMPORTED_LOCATION "${ELEMENTX_MATRIX_BRIDGE_ARCHIVE}"
)

add_library(matrix_native SHARED
    matrix_bridge_contract.cpp
    matrix_native_addon.cpp
)

target_compile_features(matrix_native PRIVATE cxx_std_17)
target_compile_options(matrix_native PRIVATE -Wall -Wextra)
target_link_libraries(matrix_native PRIVATE
    elementx_matrix_sdk_bridge
    libace_napi.z.so
    libdl.so
)
