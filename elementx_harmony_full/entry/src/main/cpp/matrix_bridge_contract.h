#ifndef ELEMENTX_MATRIX_BRIDGE_CONTRACT_H
#define ELEMENTX_MATRIX_BRIDGE_CONTRACT_H

#include <array>
#include <cstddef>
#include <cstdint>

extern "C" {
struct ElementxMatrixClientResult {
    uint32_t error_code;
    uint32_t state;
    uint64_t handle;
};

struct ElementxMatrixDataResult {
    uint32_t error_code;
    char *value;
};

uint32_t elementx_matrix_bridge_abi_version();
uint8_t elementx_matrix_bridge_sdk_linked();
uint8_t elementx_matrix_bridge_runtime_ready();
const char *elementx_matrix_bridge_status();
const char *elementx_matrix_bridge_sdk_version();
const char *elementx_matrix_bridge_error_message(uint32_t error_code);
ElementxMatrixClientResult elementx_matrix_bridge_create_client(const char *homeserver_url);
ElementxMatrixClientResult elementx_matrix_bridge_restore_client(const char *homeserver_url,
    const char *user_id, const char *device_id, const char *access_token, const char *refresh_token);
ElementxMatrixClientResult elementx_matrix_bridge_release_client(uint64_t handle);
ElementxMatrixClientResult elementx_matrix_bridge_get_client_status(uint64_t handle);
ElementxMatrixDataResult elementx_matrix_bridge_sync_rooms(uint64_t handle);
ElementxMatrixDataResult elementx_matrix_bridge_load_timeline(uint64_t handle,
    const char *room_id, const char *from_token);
ElementxMatrixDataResult elementx_matrix_bridge_send_text(uint64_t handle,
    const char *room_id, const char *body, const char *transaction_id);
void elementx_matrix_bridge_free_string(char *value);
}

namespace elementx::nativebridge {

inline constexpr const char *kContractVersion = "3";
inline constexpr const char *kAddonVersion = "0.3.0";
inline constexpr const char *kCapabilityUnavailableMessage =
    "Matrix capability is not implemented by this bridge";

struct CapabilityDescriptor {
    const char *name;
    const char *status;
    const char *detail;
};

const std::array<CapabilityDescriptor, 10> &GetUnavailableCapabilities();

}  // namespace elementx::nativebridge

#endif  // ELEMENTX_MATRIX_BRIDGE_CONTRACT_H
