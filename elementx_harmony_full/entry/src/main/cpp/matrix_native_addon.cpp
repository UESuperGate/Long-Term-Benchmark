#include "matrix_bridge_contract.h"

#include "napi/native_api.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <memory>
#include <string>
#include <utility>
#include <vector>

namespace elementx::nativebridge {
namespace {

constexpr uint32_t kErrorOk = 0;
constexpr uint32_t kErrorInvalidArgument = 1;
constexpr uint32_t kErrorInvalidHomeserverUrl = 2;
constexpr uint32_t kErrorRuntimeUnavailable = 3;
constexpr uint32_t kErrorClientBuildFailed = 4;
constexpr uint32_t kErrorClientNotFound = 5;
constexpr uint32_t kErrorHandleExhausted = 6;
constexpr uint32_t kErrorInternalFailure = 7;
constexpr uint32_t kErrorMatrixSdkUnavailable = 8;
constexpr uint32_t kErrorSessionRestoreFailed = 9;
constexpr uint32_t kErrorSyncFailed = 10;
constexpr uint32_t kErrorSerializationFailed = 11;
constexpr uint32_t kErrorRoomNotFound = 12;
constexpr uint32_t kErrorTimelineFailed = 13;
constexpr uint32_t kErrorSendFailed = 14;
constexpr uint32_t kClientStateReady = 1;
constexpr uint32_t kClientStateReleased = 2;

enum class ClientOperation {
    Create,
    Restore,
    Release,
    Status,
};

enum class DataOperation {
    SyncRooms,
    LoadTimeline,
    SendText,
};

struct ClientAsyncContext {
    napi_async_work work = nullptr;
    napi_deferred deferred = nullptr;
    ClientOperation operation = ClientOperation::Status;
    std::string homeserverUrl;
    std::string userId;
    std::string deviceId;
    std::string accessToken;
    std::string refreshToken;
    uint64_t handle = 0;
    ElementxMatrixClientResult result = {kErrorInternalFailure, 0, 0};
};

struct DataAsyncContext {
    napi_async_work work = nullptr;
    napi_deferred deferred = nullptr;
    DataOperation operation = DataOperation::SyncRooms;
    uint64_t handle = 0;
    std::string roomId;
    std::string token;
    std::string body;
    std::string transactionId;
    uint32_t errorCode = kErrorInternalFailure;
    std::string value;
};

static_assert(sizeof(ElementxMatrixClientResult) == 16, "Rust and C++ client result ABI must match");
static_assert(sizeof(ElementxMatrixDataResult) == 16, "Rust and C++ data result ABI must match");

napi_value Undefined(napi_env env)
{
    napi_value value = nullptr;
    napi_get_undefined(env, &value);
    return value;
}

bool SetString(napi_env env, napi_value object, const char *name, const char *value)
{
    napi_value property = nullptr;
    if (napi_create_string_utf8(env, value, NAPI_AUTO_LENGTH, &property) != napi_ok) {
        return false;
    }
    return napi_set_named_property(env, object, name, property) == napi_ok;
}

bool SetBoolean(napi_env env, napi_value object, const char *name, bool value)
{
    napi_value property = nullptr;
    if (napi_get_boolean(env, value, &property) != napi_ok) {
        return false;
    }
    return napi_set_named_property(env, object, name, property) == napi_ok;
}

bool SetInt32(napi_env env, napi_value object, const char *name, int32_t value)
{
    napi_value property = nullptr;
    if (napi_create_int32(env, value, &property) != napi_ok) {
        return false;
    }
    return napi_set_named_property(env, object, name, property) == napi_ok;
}

bool SetInt64(napi_env env, napi_value object, const char *name, int64_t value)
{
    napi_value property = nullptr;
    if (napi_create_int64(env, value, &property) != napi_ok) {
        return false;
    }
    return napi_set_named_property(env, object, name, property) == napi_ok;
}

bool SetNull(napi_env env, napi_value object, const char *name)
{
    napi_value property = nullptr;
    if (napi_get_null(env, &property) != napi_ok) {
        return false;
    }
    return napi_set_named_property(env, object, name, property) == napi_ok;
}

const char *ErrorCodeName(uint32_t errorCode)
{
    switch (errorCode) {
        case kErrorOk:
            return "ok";
        case kErrorInvalidArgument:
            return "invalid_argument";
        case kErrorInvalidHomeserverUrl:
            return "invalid_homeserver_url";
        case kErrorRuntimeUnavailable:
            return "runtime_unavailable";
        case kErrorClientBuildFailed:
            return "client_build_failed";
        case kErrorClientNotFound:
            return "client_not_found";
        case kErrorHandleExhausted:
            return "handle_exhausted";
        case kErrorMatrixSdkUnavailable:
            return "matrix_sdk_unavailable";
        case kErrorSessionRestoreFailed:
            return "session_restore_failed";
        case kErrorSyncFailed:
            return "sync_failed";
        case kErrorSerializationFailed:
            return "serialization_failed";
        case kErrorRoomNotFound:
            return "room_not_found";
        case kErrorTimelineFailed:
            return "timeline_failed";
        case kErrorSendFailed:
            return "send_failed";
        default:
            return "internal_failure";
    }
}

const char *ClientStateName(uint32_t state)
{
    switch (state) {
        case kClientStateReady:
            return "ready";
        case kClientStateReleased:
            return "released";
        default:
            return "none";
    }
}

bool ErrorIsRetryable(uint32_t errorCode)
{
    return errorCode == kErrorRuntimeUnavailable || errorCode == kErrorClientBuildFailed ||
        errorCode == kErrorSessionRestoreFailed || errorCode == kErrorSyncFailed ||
        errorCode == kErrorTimelineFailed || errorCode == kErrorSendFailed;
}

napi_value CreateStatus(napi_env env)
{
    const uint32_t abiVersion = elementx_matrix_bridge_abi_version();
    const bool sdkLinked = elementx_matrix_bridge_sdk_linked() != 0;
    const bool runtimeReady = elementx_matrix_bridge_runtime_ready() != 0;
    const char *availability = runtimeReady ? "ready" : (sdkLinked ? "failed" : "unavailable");

    napi_value status = nullptr;
    if (napi_create_object(env, &status) != napi_ok ||
        !SetString(env, status, "contractVersion", kContractVersion) ||
        !SetString(env, status, "addonVersion", kAddonVersion) ||
        !SetInt32(env, status, "abiVersion", static_cast<int32_t>(abiVersion)) ||
        !SetString(env, status, "availability", availability) ||
        !SetBoolean(env, status, "sdkLinked", sdkLinked) ||
        !SetString(env, status, "sdkVersion", elementx_matrix_bridge_sdk_version()) ||
        !SetString(env, status, "message", elementx_matrix_bridge_status())) {
        return Undefined(env);
    }
    return status;
}

napi_value CreateClientInfo(napi_env env, const ElementxMatrixClientResult &result)
{
    napi_value client = nullptr;
    if (napi_create_object(env, &client) != napi_ok ||
        !SetInt64(env, client, "handle", static_cast<int64_t>(result.handle)) ||
        !SetString(env, client, "state", ClientStateName(result.state))) {
        return Undefined(env);
    }
    return client;
}

napi_value CreateError(napi_env env, uint32_t errorCode)
{
    napi_value error = nullptr;
    if (napi_create_object(env, &error) != napi_ok ||
        !SetString(env, error, "code", ErrorCodeName(errorCode)) ||
        !SetString(env, error, "message", elementx_matrix_bridge_error_message(errorCode)) ||
        !SetBoolean(env, error, "retryable", ErrorIsRetryable(errorCode)) ||
        !SetInt32(env, error, "nativeCode", static_cast<int32_t>(errorCode))) {
        return Undefined(env);
    }
    return error;
}

napi_value CreateClientOperationResult(napi_env env, const ElementxMatrixClientResult &result)
{
    napi_value value = nullptr;
    if (napi_create_object(env, &value) != napi_ok ||
        !SetBoolean(env, value, "ok", result.error_code == kErrorOk)) {
        return Undefined(env);
    }

    if (result.error_code == kErrorOk) {
        napi_value client = CreateClientInfo(env, result);
        if (napi_set_named_property(env, value, "client", client) != napi_ok ||
            !SetNull(env, value, "error")) {
            return Undefined(env);
        }
    } else {
        napi_value error = CreateError(env, result.error_code);
        if (!SetNull(env, value, "client") ||
            napi_set_named_property(env, value, "error", error) != napi_ok) {
            return Undefined(env);
        }
    }
    return value;
}

napi_value ResolveImmediate(napi_env env, const ElementxMatrixClientResult &result)
{
    napi_deferred deferred = nullptr;
    napi_value promise = nullptr;
    if (napi_create_promise(env, &deferred, &promise) != napi_ok) {
        return Undefined(env);
    }
    napi_value value = CreateClientOperationResult(env, result);
    if (napi_resolve_deferred(env, deferred, value) != napi_ok) {
        return Undefined(env);
    }
    return promise;
}

napi_value CreateDataOperationResult(napi_env env, uint32_t errorCode, const std::string &data)
{
    napi_value value = nullptr;
    if (napi_create_object(env, &value) != napi_ok || !SetBoolean(env, value, "ok", errorCode == kErrorOk)) {
        return Undefined(env);
    }
    if (errorCode == kErrorOk) {
        if (!SetString(env, value, "value", data.c_str()) || !SetNull(env, value, "error")) {
            return Undefined(env);
        }
    } else {
        napi_value error = CreateError(env, errorCode);
        if (!SetNull(env, value, "value") || napi_set_named_property(env, value, "error", error) != napi_ok) {
            return Undefined(env);
        }
    }
    return value;
}

napi_value ResolveDataImmediate(napi_env env, uint32_t errorCode)
{
    napi_deferred deferred = nullptr;
    napi_value promise = nullptr;
    if (napi_create_promise(env, &deferred, &promise) != napi_ok) {
        return Undefined(env);
    }
    napi_value value = CreateDataOperationResult(env, errorCode, "");
    if (napi_resolve_deferred(env, deferred, value) != napi_ok) {
        return Undefined(env);
    }
    return promise;
}

void ExecuteClientOperation(napi_env env, void *data)
{
    (void)env;
    auto *context = static_cast<ClientAsyncContext *>(data);
    switch (context->operation) {
        case ClientOperation::Create:
            context->result = elementx_matrix_bridge_create_client(context->homeserverUrl.c_str());
            break;
        case ClientOperation::Restore:
            context->result = elementx_matrix_bridge_restore_client(
                context->homeserverUrl.c_str(), context->userId.c_str(), context->deviceId.c_str(),
                context->accessToken.c_str(), context->refreshToken.c_str());
            std::fill(context->accessToken.begin(), context->accessToken.end(), '\0');
            std::fill(context->refreshToken.begin(), context->refreshToken.end(), '\0');
            break;
        case ClientOperation::Release:
            context->result = elementx_matrix_bridge_release_client(context->handle);
            break;
        case ClientOperation::Status:
            context->result = elementx_matrix_bridge_get_client_status(context->handle);
            break;
    }
}

void CompleteClientOperation(napi_env env, napi_status status, void *data)
{
    std::unique_ptr<ClientAsyncContext> context(static_cast<ClientAsyncContext *>(data));
    if (status != napi_ok) {
        context->result = {kErrorInternalFailure, 0, 0};
    }
    napi_value value = CreateClientOperationResult(env, context->result);
    napi_resolve_deferred(env, context->deferred, value);
    napi_delete_async_work(env, context->work);
}

napi_value QueueClientOperation(napi_env env, std::unique_ptr<ClientAsyncContext> context)
{
    napi_value promise = nullptr;
    if (napi_create_promise(env, &context->deferred, &promise) != napi_ok) {
        return Undefined(env);
    }

    napi_value resourceName = nullptr;
    if (napi_create_string_utf8(env, "ElementXMatrixClientOperation", NAPI_AUTO_LENGTH, &resourceName) != napi_ok ||
        napi_create_async_work(env, nullptr, resourceName, ExecuteClientOperation, CompleteClientOperation,
            context.get(), &context->work) != napi_ok) {
        if (context->work != nullptr) {
            napi_delete_async_work(env, context->work);
        }
        napi_value value = CreateClientOperationResult(env, {kErrorInternalFailure, 0, 0});
        napi_resolve_deferred(env, context->deferred, value);
        return promise;
    }
    if (napi_queue_async_work(env, context->work) != napi_ok) {
        napi_delete_async_work(env, context->work);
        napi_value value = CreateClientOperationResult(env, {kErrorInternalFailure, 0, 0});
        napi_resolve_deferred(env, context->deferred, value);
        return promise;
    }
    context.release();
    return promise;
}

void ExecuteDataOperation(napi_env env, void *data)
{
    (void)env;
    auto *context = static_cast<DataAsyncContext *>(data);
    ElementxMatrixDataResult result = {kErrorInternalFailure, nullptr};
    switch (context->operation) {
        case DataOperation::SyncRooms:
            result = elementx_matrix_bridge_sync_rooms(context->handle);
            break;
        case DataOperation::LoadTimeline:
            result = elementx_matrix_bridge_load_timeline(
                context->handle, context->roomId.c_str(), context->token.c_str());
            break;
        case DataOperation::SendText:
            result = elementx_matrix_bridge_send_text(
                context->handle, context->roomId.c_str(), context->body.c_str(), context->transactionId.c_str());
            break;
    }
    context->errorCode = result.error_code;
    if (result.value != nullptr) {
        context->value.assign(result.value);
        elementx_matrix_bridge_free_string(result.value);
    }
}

void CompleteDataOperation(napi_env env, napi_status status, void *data)
{
    std::unique_ptr<DataAsyncContext> context(static_cast<DataAsyncContext *>(data));
    if (status != napi_ok) {
        context->errorCode = kErrorInternalFailure;
        context->value.clear();
    }
    napi_value value = CreateDataOperationResult(env, context->errorCode, context->value);
    napi_resolve_deferred(env, context->deferred, value);
    napi_delete_async_work(env, context->work);
}

napi_value QueueDataOperation(napi_env env, std::unique_ptr<DataAsyncContext> context)
{
    napi_value promise = nullptr;
    if (napi_create_promise(env, &context->deferred, &promise) != napi_ok) {
        return Undefined(env);
    }
    napi_value resourceName = nullptr;
    if (napi_create_string_utf8(env, "ElementXMatrixDataOperation", NAPI_AUTO_LENGTH, &resourceName) != napi_ok ||
        napi_create_async_work(env, nullptr, resourceName, ExecuteDataOperation, CompleteDataOperation,
            context.get(), &context->work) != napi_ok) {
        if (context->work != nullptr) {
            napi_delete_async_work(env, context->work);
        }
        napi_value value = CreateDataOperationResult(env, kErrorInternalFailure, "");
        napi_resolve_deferred(env, context->deferred, value);
        return promise;
    }
    if (napi_queue_async_work(env, context->work) != napi_ok) {
        napi_delete_async_work(env, context->work);
        napi_value value = CreateDataOperationResult(env, kErrorInternalFailure, "");
        napi_resolve_deferred(env, context->deferred, value);
        return promise;
    }
    context.release();
    return promise;
}

bool ReadStringArgument(napi_env env, napi_callback_info info, std::string &value)
{
    size_t argc = 1;
    napi_value argv[1] = {nullptr};
    if (napi_get_cb_info(env, info, &argc, argv, nullptr, nullptr) != napi_ok || argc != 1) {
        return false;
    }
    napi_valuetype valueType = napi_undefined;
    if (napi_typeof(env, argv[0], &valueType) != napi_ok || valueType != napi_string) {
        return false;
    }
    size_t length = 0;
    if (napi_get_value_string_utf8(env, argv[0], nullptr, 0, &length) != napi_ok || length > 2048) {
        return false;
    }
    std::vector<char> buffer(length + 1, '\0');
    size_t copied = 0;
    if (napi_get_value_string_utf8(env, argv[0], buffer.data(), buffer.size(), &copied) != napi_ok) {
        return false;
    }
    value.assign(buffer.data(), copied);
    return true;
}

bool ReadStringValue(napi_env env, napi_value input, std::size_t maxLength, std::string &value)
{
    napi_valuetype valueType = napi_undefined;
    if (napi_typeof(env, input, &valueType) != napi_ok || valueType != napi_string) {
        return false;
    }
    size_t length = 0;
    if (napi_get_value_string_utf8(env, input, nullptr, 0, &length) != napi_ok || length > maxLength) {
        return false;
    }
    std::vector<char> buffer(length + 1, '\0');
    size_t copied = 0;
    if (napi_get_value_string_utf8(env, input, buffer.data(), buffer.size(), &copied) != napi_ok) {
        return false;
    }
    value.assign(buffer.data(), copied);
    return true;
}

bool ReadRestoreArguments(napi_env env, napi_callback_info info, ClientAsyncContext &context)
{
    size_t argc = 5;
    napi_value argv[5] = {nullptr, nullptr, nullptr, nullptr, nullptr};
    if (napi_get_cb_info(env, info, &argc, argv, nullptr, nullptr) != napi_ok || argc != 5) {
        return false;
    }
    return ReadStringValue(env, argv[0], 2048, context.homeserverUrl) &&
        ReadStringValue(env, argv[1], 512, context.userId) &&
        ReadStringValue(env, argv[2], 512, context.deviceId) &&
        ReadStringValue(env, argv[3], 65'536, context.accessToken) &&
        ReadStringValue(env, argv[4], 65'536, context.refreshToken);
}

bool ReadHandleArgument(napi_env env, napi_callback_info info, uint64_t &handle)
{
    size_t argc = 1;
    napi_value argv[1] = {nullptr};
    if (napi_get_cb_info(env, info, &argc, argv, nullptr, nullptr) != napi_ok || argc != 1) {
        return false;
    }
    napi_valuetype valueType = napi_undefined;
    double numericHandle = 0;
    constexpr double kMaxSafeHandle = 9'007'199'254'740'991.0;
    if (napi_typeof(env, argv[0], &valueType) != napi_ok || valueType != napi_number ||
        napi_get_value_double(env, argv[0], &numericHandle) != napi_ok ||
        !std::isfinite(numericHandle) || numericHandle < 1 || numericHandle > kMaxSafeHandle ||
        std::trunc(numericHandle) != numericHandle) {
        return false;
    }
    handle = static_cast<uint64_t>(numericHandle);
    return true;
}

bool ReadHandleValue(napi_env env, napi_value input, uint64_t &handle)
{
    napi_valuetype valueType = napi_undefined;
    double numericHandle = 0;
    constexpr double kMaxSafeHandle = 9'007'199'254'740'991.0;
    if (napi_typeof(env, input, &valueType) != napi_ok || valueType != napi_number ||
        napi_get_value_double(env, input, &numericHandle) != napi_ok ||
        !std::isfinite(numericHandle) || numericHandle < 1 || numericHandle > kMaxSafeHandle ||
        std::trunc(numericHandle) != numericHandle) {
        return false;
    }
    handle = static_cast<uint64_t>(numericHandle);
    return true;
}

bool ReadTimelineArguments(napi_env env, napi_callback_info info, DataAsyncContext &context)
{
    size_t argc = 3;
    napi_value argv[3] = {nullptr, nullptr, nullptr};
    if (napi_get_cb_info(env, info, &argc, argv, nullptr, nullptr) != napi_ok || argc != 3) {
        return false;
    }
    return ReadHandleValue(env, argv[0], context.handle) &&
        ReadStringValue(env, argv[1], 512, context.roomId) &&
        ReadStringValue(env, argv[2], 65'536, context.token);
}

bool ReadSendArguments(napi_env env, napi_callback_info info, DataAsyncContext &context)
{
    size_t argc = 4;
    napi_value argv[4] = {nullptr, nullptr, nullptr, nullptr};
    if (napi_get_cb_info(env, info, &argc, argv, nullptr, nullptr) != napi_ok || argc != 4) {
        return false;
    }
    return ReadHandleValue(env, argv[0], context.handle) &&
        ReadStringValue(env, argv[1], 512, context.roomId) &&
        ReadStringValue(env, argv[2], 65'536, context.body) &&
        ReadStringValue(env, argv[3], 512, context.transactionId);
}

napi_value GetBridgeStatus(napi_env env, napi_callback_info info)
{
    (void)info;
    return CreateStatus(env);
}

napi_value GetCapabilities(napi_env env, napi_callback_info info)
{
    (void)info;
    const bool runtimeReady = elementx_matrix_bridge_runtime_ready() != 0;
    const auto &capabilities = GetUnavailableCapabilities();
    napi_value array = nullptr;
    if (napi_create_array_with_length(env, capabilities.size(), &array) != napi_ok) {
        return Undefined(env);
    }

    for (std::size_t index = 0; index < capabilities.size(); ++index) {
        napi_value item = nullptr;
        const CapabilityDescriptor &capability = capabilities[index];
        const bool isRuntimeCapability = std::strcmp(capability.name, "client_runtime") == 0 ||
            std::strcmp(capability.name, "authentication") == 0 ||
            std::strcmp(capability.name, "session_restoration") == 0 ||
            std::strcmp(capability.name, "room_list") == 0 ||
            std::strcmp(capability.name, "timeline") == 0;
        const char *status = isRuntimeCapability && runtimeReady ? "available" : capability.status;
        const char *detail = isRuntimeCapability && runtimeReady
            ? "Matrix Client creation, authenticated session restoration, status, and release are available"
            : capability.detail;
        if (napi_create_object(env, &item) != napi_ok ||
            !SetString(env, item, "capability", capability.name) ||
            !SetString(env, item, "status", status) ||
            !SetString(env, item, "detail", detail) ||
            napi_set_element(env, array, static_cast<uint32_t>(index), item) != napi_ok) {
            return Undefined(env);
        }
    }
    return array;
}

napi_value CreateClient(napi_env env, napi_callback_info info)
{
    std::string homeserverUrl;
    if (!ReadStringArgument(env, info, homeserverUrl)) {
        return ResolveImmediate(env, {kErrorInvalidArgument, 0, 0});
    }
    auto context = std::make_unique<ClientAsyncContext>();
    context->operation = ClientOperation::Create;
    context->homeserverUrl = std::move(homeserverUrl);
    return QueueClientOperation(env, std::move(context));
}

napi_value ReleaseClient(napi_env env, napi_callback_info info)
{
    uint64_t handle = 0;
    if (!ReadHandleArgument(env, info, handle)) {
        return ResolveImmediate(env, {kErrorInvalidArgument, 0, 0});
    }
    auto context = std::make_unique<ClientAsyncContext>();
    context->operation = ClientOperation::Release;
    context->handle = handle;
    return QueueClientOperation(env, std::move(context));
}

napi_value RestoreClient(napi_env env, napi_callback_info info)
{
    auto context = std::make_unique<ClientAsyncContext>();
    if (!ReadRestoreArguments(env, info, *context)) {
        return ResolveImmediate(env, {kErrorInvalidArgument, 0, 0});
    }
    context->operation = ClientOperation::Restore;
    return QueueClientOperation(env, std::move(context));
}

napi_value GetClientStatus(napi_env env, napi_callback_info info)
{
    uint64_t handle = 0;
    if (!ReadHandleArgument(env, info, handle)) {
        return ResolveImmediate(env, {kErrorInvalidArgument, 0, 0});
    }
    auto context = std::make_unique<ClientAsyncContext>();
    context->operation = ClientOperation::Status;
    context->handle = handle;
    return QueueClientOperation(env, std::move(context));
}

napi_value SyncRooms(napi_env env, napi_callback_info info)
{
    uint64_t handle = 0;
    if (!ReadHandleArgument(env, info, handle)) {
        return ResolveDataImmediate(env, kErrorInvalidArgument);
    }
    auto context = std::make_unique<DataAsyncContext>();
    context->operation = DataOperation::SyncRooms;
    context->handle = handle;
    return QueueDataOperation(env, std::move(context));
}

napi_value LoadTimeline(napi_env env, napi_callback_info info)
{
    auto context = std::make_unique<DataAsyncContext>();
    if (!ReadTimelineArguments(env, info, *context)) {
        return ResolveDataImmediate(env, kErrorInvalidArgument);
    }
    context->operation = DataOperation::LoadTimeline;
    return QueueDataOperation(env, std::move(context));
}

napi_value SendText(napi_env env, napi_callback_info info)
{
    auto context = std::make_unique<DataAsyncContext>();
    if (!ReadSendArguments(env, info, *context)) {
        return ResolveDataImmediate(env, kErrorInvalidArgument);
    }
    context->operation = DataOperation::SendText;
    return QueueDataOperation(env, std::move(context));
}

napi_value Init(napi_env env, napi_value exports)
{
    napi_property_descriptor descriptors[] = {
        {"getBridgeStatus", nullptr, GetBridgeStatus, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"getCapabilities", nullptr, GetCapabilities, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"createClient", nullptr, CreateClient, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"restoreClient", nullptr, RestoreClient, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"releaseClient", nullptr, ReleaseClient, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"getClientStatus", nullptr, GetClientStatus, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"syncRooms", nullptr, SyncRooms, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"loadTimeline", nullptr, LoadTimeline, nullptr, nullptr, nullptr, napi_default, nullptr},
        {"sendText", nullptr, SendText, nullptr, nullptr, nullptr, napi_default, nullptr},
    };
    if (napi_define_properties(env, exports, sizeof(descriptors) / sizeof(descriptors[0]), descriptors) != napi_ok) {
        return Undefined(env);
    }
    return exports;
}

}  // namespace
}  // namespace elementx::nativebridge

static napi_module g_matrixNativeModule = {
    1,
    0,
    nullptr,
    elementx::nativebridge::Init,
    "matrix_native",
    nullptr,
    {nullptr, nullptr, nullptr, nullptr},
};

extern "C" __attribute__((constructor)) void RegisterMatrixNativeModule()
{
    napi_module_register(&g_matrixNativeModule);
}
