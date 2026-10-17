#include "matrix_bridge_contract.h"

namespace elementx::nativebridge {

const std::array<CapabilityDescriptor, 10> &GetUnavailableCapabilities()
{
    static const std::array<CapabilityDescriptor, 10> capabilities = {{
        {"client_runtime", "unavailable", kCapabilityUnavailableMessage},
        {"authentication", "unavailable", kCapabilityUnavailableMessage},
        {"session_restoration", "unavailable", kCapabilityUnavailableMessage},
        {"sliding_sync", "unavailable", kCapabilityUnavailableMessage},
        {"room_list", "unavailable", kCapabilityUnavailableMessage},
        {"timeline", "unavailable", kCapabilityUnavailableMessage},
        {"encryption", "unavailable", kCapabilityUnavailableMessage},
        {"session_verification", "unavailable", kCapabilityUnavailableMessage},
        {"media", "unavailable", kCapabilityUnavailableMessage},
        {"push_notifications", "unavailable", kCapabilityUnavailableMessage},
    }};
    return capabilities;
}

}  // namespace elementx::nativebridge
