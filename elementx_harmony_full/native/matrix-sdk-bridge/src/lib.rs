//! Stable C ABI boundary between OpenHarmony N-API code and Matrix Rust SDK.

use std::ffi::c_char;
use std::ffi::CString;

use serde::Serialize;

#[cfg(feature = "matrix-sdk")]
use std::{
    collections::HashMap,
    ffi::CStr,
    panic::{AssertUnwindSafe, catch_unwind},
    sync::{
        Mutex, OnceLock,
        atomic::{AtomicU64, Ordering},
    },
};

pub const ABI_VERSION: u32 = 3;
#[cfg(feature = "matrix-sdk")]
const MAX_HOMESERVER_URL_LENGTH: usize = 2048;
#[cfg(feature = "matrix-sdk")]
const MAX_MATRIX_ID_LENGTH: usize = 512;
#[cfg(feature = "matrix-sdk")]
const MAX_TOKEN_LENGTH: usize = 65_536;
#[cfg(feature = "matrix-sdk")]
const MAX_MESSAGE_LENGTH: usize = 65_536;
#[cfg(feature = "matrix-sdk")]
const MAX_SAFE_HANDLE: u64 = 9_007_199_254_740_991;

const STATUS_UNAVAILABLE: &[u8] = b"matrix_sdk_unavailable\0";
const STATUS_READY: &[u8] = b"matrix_client_runtime_ready\0";
const STATUS_RUNTIME_UNAVAILABLE: &[u8] = b"matrix_runtime_unavailable\0";
const SDK_VERSION_UNAVAILABLE: &[u8] = b"\0";
const SDK_VERSION_LINKED: &[u8] = b"0.16.0@2214aded\0";

const MESSAGE_OK: &[u8] = b"Operation completed\0";
const MESSAGE_INVALID_ARGUMENT: &[u8] = b"A required argument is missing or invalid\0";
const MESSAGE_INVALID_HOMESERVER_URL: &[u8] = b"Homeserver URL must be an HTTP or HTTPS URL with a host and no credentials\0";
const MESSAGE_RUNTIME_UNAVAILABLE: &[u8] = b"Matrix runtime could not be initialized\0";
const MESSAGE_CLIENT_BUILD_FAILED: &[u8] = b"Matrix Client construction failed\0";
const MESSAGE_SESSION_RESTORE_FAILED: &[u8] = b"Matrix SDK session restoration failed\0";
const MESSAGE_SYNC_FAILED: &[u8] = b"Matrix SDK sync failed\0";
const MESSAGE_SERIALIZATION_FAILED: &[u8] = b"Matrix bridge response serialization failed\0";
const MESSAGE_ROOM_NOT_FOUND: &[u8] = b"Matrix room does not exist in the authenticated client\0";
const MESSAGE_TIMELINE_FAILED: &[u8] = b"Matrix room timeline request failed\0";
const MESSAGE_SEND_FAILED: &[u8] = b"Matrix room message send failed\0";
const MESSAGE_CLIENT_NOT_FOUND: &[u8] = b"Matrix Client handle does not exist\0";
const MESSAGE_HANDLE_EXHAUSTED: &[u8] = b"Matrix Client handle space is exhausted\0";
const MESSAGE_INTERNAL_FAILURE: &[u8] = b"Matrix bridge internal failure\0";
const MESSAGE_SDK_UNAVAILABLE: &[u8] = b"Matrix SDK is not linked into this application\0";

#[repr(u32)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum BridgeErrorCode {
    Ok = 0,
    InvalidArgument = 1,
    InvalidHomeserverUrl = 2,
    RuntimeUnavailable = 3,
    ClientBuildFailed = 4,
    ClientNotFound = 5,
    HandleExhausted = 6,
    InternalFailure = 7,
    MatrixSdkUnavailable = 8,
    SessionRestoreFailed = 9,
    SyncFailed = 10,
    SerializationFailed = 11,
    RoomNotFound = 12,
    TimelineFailed = 13,
    SendFailed = 14,
}

#[repr(u32)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum BridgeClientState {
    None = 0,
    Ready = 1,
    Released = 2,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct BridgeClientResult {
    pub error_code: u32,
    pub state: u32,
    pub handle: u64,
}

#[repr(C)]
#[derive(Debug)]
pub struct BridgeDataResult {
    pub error_code: u32,
    pub value: *mut c_char,
}

impl BridgeDataResult {
    #[cfg(feature = "matrix-sdk")]
    fn success(value: String) -> Self {
        match CString::new(value) {
            Ok(value) => Self { error_code: BridgeErrorCode::Ok as u32, value: value.into_raw() },
            Err(_) => Self::failure(BridgeErrorCode::SerializationFailed),
        }
    }

    fn failure(code: BridgeErrorCode) -> Self {
        Self { error_code: code as u32, value: std::ptr::null_mut() }
    }
}

#[cfg(feature = "matrix-sdk")]
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct RoomSummaryPayload {
    room_id: String,
    display_name: String,
    canonical_alias: Option<String>,
    avatar_url: Option<String>,
    membership: &'static str,
    category: &'static str,
    is_favorite: bool,
    is_direct: bool,
    is_marked_unread: bool,
    unread_notification_count: u64,
    unread_mention_count: u64,
    active_members_count: u64,
    latest_event_timestamp_ms: Option<u64>,
    latest_event_preview: Option<String>,
}

#[cfg(feature = "matrix-sdk")]
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct RoomListPayload {
    rooms: Vec<RoomSummaryPayload>,
    total_count: usize,
}

#[cfg(feature = "matrix-sdk")]
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct TimelinePayload {
    events: Vec<serde_json::Value>,
    end: Option<String>,
}

#[cfg(feature = "matrix-sdk")]
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct SendPayload {
    event_id: String,
}

#[cfg(feature = "matrix-sdk")]
fn normalize_timeline_event(mut event: serde_json::Value) -> serde_json::Value {
    if let Some(content) = event.get_mut("content").and_then(serde_json::Value::as_object_mut) {
        if let Some(mut relation) = content.remove("m.relates_to") {
            if let Some(relation_object) = relation.as_object_mut() {
                if let Some(reply) = relation_object.remove("m.in_reply_to") {
                    relation_object.insert("mInReplyTo".to_owned(), reply);
                }
            }
            content.insert("mRelatesTo".to_owned(), relation);
        }
    }
    event
}

impl BridgeClientResult {
    #[cfg(feature = "matrix-sdk")]
    fn success(handle: u64, state: BridgeClientState) -> Self {
        Self { error_code: BridgeErrorCode::Ok as u32, state: state as u32, handle }
    }

    fn failure(code: BridgeErrorCode) -> Self {
        Self { error_code: code as u32, state: BridgeClientState::None as u32, handle: 0 }
    }
}

#[cfg(feature = "matrix-sdk")]
// The runtime is process-scoped. N-API work runs outside its worker threads,
// and every Client remains owned by the registry until explicit release.
static RUNTIME: OnceLock<Result<tokio::runtime::Runtime, BridgeErrorCode>> = OnceLock::new();
#[cfg(feature = "matrix-sdk")]
static CLIENTS: OnceLock<Mutex<HashMap<u64, matrix_sdk::Client>>> = OnceLock::new();
#[cfg(feature = "matrix-sdk")]
static NEXT_HANDLE: AtomicU64 = AtomicU64::new(1);

#[cfg(feature = "matrix-sdk")]
fn runtime() -> Result<&'static tokio::runtime::Runtime, BridgeErrorCode> {
    RUNTIME
        .get_or_init(|| {
            tokio::runtime::Builder::new_multi_thread()
                .worker_threads(2)
                .thread_name("elementx-matrix")
                .build()
                .map_err(|_| BridgeErrorCode::RuntimeUnavailable)
        })
        .as_ref()
        .map_err(|code| *code)
}

#[cfg(feature = "matrix-sdk")]
fn clients() -> &'static Mutex<HashMap<u64, matrix_sdk::Client>> {
    CLIENTS.get_or_init(|| Mutex::new(HashMap::new()))
}

#[cfg(feature = "matrix-sdk")]
fn parse_homeserver_url(raw_url: &str) -> Result<matrix_sdk::reqwest::Url, BridgeErrorCode> {
    if raw_url.is_empty()
        || raw_url.len() > MAX_HOMESERVER_URL_LENGTH
        || raw_url.trim() != raw_url
    {
        return Err(BridgeErrorCode::InvalidHomeserverUrl);
    }

    let url = matrix_sdk::reqwest::Url::parse(raw_url)
        .map_err(|_| BridgeErrorCode::InvalidHomeserverUrl)?;
    if !matches!(url.scheme(), "http" | "https")
        || url.host_str().is_none()
        || !url.username().is_empty()
        || url.password().is_some()
        || url.query().is_some()
        || url.fragment().is_some()
    {
        return Err(BridgeErrorCode::InvalidHomeserverUrl);
    }
    Ok(url)
}

#[cfg(feature = "matrix-sdk")]
fn next_handle() -> Result<u64, BridgeErrorCode> {
    let handle = NEXT_HANDLE.fetch_add(1, Ordering::Relaxed);
    if handle == 0 || handle > MAX_SAFE_HANDLE {
        Err(BridgeErrorCode::HandleExhausted)
    } else {
        Ok(handle)
    }
}

#[cfg(feature = "matrix-sdk")]
fn create_client(raw_url: *const c_char) -> BridgeClientResult {
    if raw_url.is_null() {
        return BridgeClientResult::failure(BridgeErrorCode::InvalidArgument);
    }

    let raw_url = match unsafe { CStr::from_ptr(raw_url) }.to_str() {
        Ok(value) => value,
        Err(_) => return BridgeClientResult::failure(BridgeErrorCode::InvalidArgument),
    };
    let homeserver_url = match parse_homeserver_url(raw_url) {
        Ok(value) => value,
        Err(code) => return BridgeClientResult::failure(code),
    };
    let runtime = match runtime() {
        Ok(value) => value,
        Err(code) => return BridgeClientResult::failure(code),
    };

    let client = match runtime.block_on(
        matrix_sdk::Client::builder()
            .homeserver_url(homeserver_url.as_str())
            .build(),
    ) {
        Ok(value) => value,
        Err(_) => return BridgeClientResult::failure(BridgeErrorCode::ClientBuildFailed),
    };
    let handle = match next_handle() {
        Ok(value) => value,
        Err(code) => return BridgeClientResult::failure(code),
    };
    let mut registry = match clients().lock() {
        Ok(value) => value,
        Err(_) => return BridgeClientResult::failure(BridgeErrorCode::InternalFailure),
    };
    registry.insert(handle, client);
    BridgeClientResult::success(handle, BridgeClientState::Ready)
}

#[cfg(feature = "matrix-sdk")]
fn read_string(raw: *const c_char, max_length: usize) -> Result<String, BridgeErrorCode> {
    if raw.is_null() {
        return Err(BridgeErrorCode::InvalidArgument);
    }
    let value = unsafe { CStr::from_ptr(raw) }
        .to_str()
        .map_err(|_| BridgeErrorCode::InvalidArgument)?;
    if value.is_empty() || value.len() > max_length {
        return Err(BridgeErrorCode::InvalidArgument);
    }
    Ok(value.to_owned())
}

#[cfg(feature = "matrix-sdk")]
fn read_optional_string(raw: *const c_char, max_length: usize) -> Result<Option<String>, BridgeErrorCode> {
    if raw.is_null() {
        return Ok(None);
    }
    let value = unsafe { CStr::from_ptr(raw) }
        .to_str()
        .map_err(|_| BridgeErrorCode::InvalidArgument)?;
    if value.len() > max_length {
        return Err(BridgeErrorCode::InvalidArgument);
    }
    Ok((!value.is_empty()).then(|| value.to_owned()))
}

#[cfg(feature = "matrix-sdk")]
fn restore_client(
    raw_url: *const c_char,
    raw_user_id: *const c_char,
    raw_device_id: *const c_char,
    raw_access_token: *const c_char,
    raw_refresh_token: *const c_char,
) -> BridgeClientResult {
    let raw_url = match read_string(raw_url, MAX_HOMESERVER_URL_LENGTH) {
        Ok(value) => value,
        Err(code) => return BridgeClientResult::failure(code),
    };
    let homeserver_url = match parse_homeserver_url(&raw_url) {
        Ok(value) => value,
        Err(code) => return BridgeClientResult::failure(code),
    };
    let user_id = match read_string(raw_user_id, MAX_MATRIX_ID_LENGTH)
        .and_then(|value| value.parse::<matrix_sdk::ruma::OwnedUserId>()
            .map_err(|_| BridgeErrorCode::InvalidArgument))
    {
        Ok(value) => value,
        Err(code) => return BridgeClientResult::failure(code),
    };
    let device_id = match read_string(raw_device_id, MAX_MATRIX_ID_LENGTH) {
        Ok(value) => matrix_sdk::ruma::OwnedDeviceId::from(value),
        Err(code) => return BridgeClientResult::failure(code),
    };
    let access_token = match read_string(raw_access_token, MAX_TOKEN_LENGTH) {
        Ok(value) => value,
        Err(code) => return BridgeClientResult::failure(code),
    };
    let refresh_token = match read_optional_string(raw_refresh_token, MAX_TOKEN_LENGTH) {
        Ok(value) => value,
        Err(code) => return BridgeClientResult::failure(code),
    };
    let runtime = match runtime() {
        Ok(value) => value,
        Err(code) => return BridgeClientResult::failure(code),
    };
    let client = match runtime.block_on(
        matrix_sdk::Client::builder()
            .homeserver_url(homeserver_url.as_str())
            .build(),
    ) {
        Ok(value) => value,
        Err(_) => return BridgeClientResult::failure(BridgeErrorCode::ClientBuildFailed),
    };
    let session = matrix_sdk::AuthSession::Matrix(
        matrix_sdk::authentication::matrix::MatrixSession {
            meta: matrix_sdk::SessionMeta { user_id, device_id },
            tokens: matrix_sdk::SessionTokens { access_token, refresh_token },
        },
    );
    if runtime.block_on(client.restore_session(session)).is_err() {
        return BridgeClientResult::failure(BridgeErrorCode::SessionRestoreFailed);
    }
    let handle = match next_handle() {
        Ok(value) => value,
        Err(code) => return BridgeClientResult::failure(code),
    };
    let mut registry = match clients().lock() {
        Ok(value) => value,
        Err(_) => return BridgeClientResult::failure(BridgeErrorCode::InternalFailure),
    };
    registry.insert(handle, client);
    BridgeClientResult::success(handle, BridgeClientState::Ready)
}

#[cfg(feature = "matrix-sdk")]
fn release_client(handle: u64) -> BridgeClientResult {
    if handle == 0 || handle > MAX_SAFE_HANDLE {
        return BridgeClientResult::failure(BridgeErrorCode::InvalidArgument);
    }
    let mut registry = match clients().lock() {
        Ok(value) => value,
        Err(_) => return BridgeClientResult::failure(BridgeErrorCode::InternalFailure),
    };
    let removed_client = registry.remove(&handle);
    drop(registry);
    if removed_client.is_some() {
        BridgeClientResult::success(handle, BridgeClientState::Released)
    } else {
        BridgeClientResult::failure(BridgeErrorCode::ClientNotFound)
    }
}

#[cfg(feature = "matrix-sdk")]
fn client_status(handle: u64) -> BridgeClientResult {
    if handle == 0 || handle > MAX_SAFE_HANDLE {
        return BridgeClientResult::failure(BridgeErrorCode::InvalidArgument);
    }
    let registry = match clients().lock() {
        Ok(value) => value,
        Err(_) => return BridgeClientResult::failure(BridgeErrorCode::InternalFailure),
    };
    if registry.contains_key(&handle) {
        BridgeClientResult::success(handle, BridgeClientState::Ready)
    } else {
        BridgeClientResult::failure(BridgeErrorCode::ClientNotFound)
    }
}

#[cfg(feature = "matrix-sdk")]
fn client_for_handle(handle: u64) -> Result<matrix_sdk::Client, BridgeErrorCode> {
    if handle == 0 || handle > MAX_SAFE_HANDLE {
        return Err(BridgeErrorCode::InvalidArgument);
    }
    let registry = clients().lock().map_err(|_| BridgeErrorCode::InternalFailure)?;
    registry.get(&handle).cloned().ok_or(BridgeErrorCode::ClientNotFound)
}

#[cfg(feature = "matrix-sdk")]
fn sync_rooms(handle: u64) -> BridgeDataResult {
    let client = match client_for_handle(handle) {
        Ok(value) => value,
        Err(code) => return BridgeDataResult::failure(code),
    };
    let runtime = match runtime() {
        Ok(value) => value,
        Err(code) => return BridgeDataResult::failure(code),
    };
    if runtime.block_on(client.sync_once(
        matrix_sdk::config::SyncSettings::default().timeout(std::time::Duration::from_secs(0)),
    )).is_err() {
        return BridgeDataResult::failure(BridgeErrorCode::SyncFailed);
    }
    let rooms = runtime.block_on(async {
        let mut payloads = Vec::new();
        for room in client.rooms() {
            let membership = match room.state() {
                matrix_sdk::RoomState::Joined => "joined",
                matrix_sdk::RoomState::Invited => "invited",
                matrix_sdk::RoomState::Left | matrix_sdk::RoomState::Banned => "left",
                matrix_sdk::RoomState::Knocked => "knocked",
            };
            let display_name = room.display_name().await
                .map(|value| value.to_string())
                .unwrap_or_else(|_| room.room_id().to_string());
            let is_direct = room.is_direct().await.unwrap_or(false);
            payloads.push(RoomSummaryPayload {
                room_id: room.room_id().to_string(),
                display_name,
                canonical_alias: room.canonical_alias().map(|value| value.to_string()),
                avatar_url: room.avatar_url().map(|value| value.to_string()),
                membership,
                category: if room.is_space() { "space" } else if is_direct { "people" } else { "group" },
                is_favorite: room.is_favourite(),
                is_direct,
                is_marked_unread: room.is_marked_unread(),
                unread_notification_count: room.num_unread_notifications(),
                unread_mention_count: room.num_unread_mentions(),
                active_members_count: room.active_members_count(),
                latest_event_timestamp_ms: room.latest_event_timestamp().map(|value| value.get().into()),
                latest_event_preview: None,
            });
        }
        payloads
    });
    let total_count = rooms.len();
    match serde_json::to_string(&RoomListPayload { rooms, total_count }) {
        Ok(value) => BridgeDataResult::success(value),
        Err(_) => BridgeDataResult::failure(BridgeErrorCode::SerializationFailed),
    }
}

#[cfg(feature = "matrix-sdk")]
fn load_timeline(handle: u64, raw_room_id: *const c_char, raw_from: *const c_char) -> BridgeDataResult {
    let client = match client_for_handle(handle) {
        Ok(value) => value,
        Err(code) => return BridgeDataResult::failure(code),
    };
    let room_id = match read_string(raw_room_id, MAX_MATRIX_ID_LENGTH)
        .and_then(|value| value.parse::<matrix_sdk::ruma::OwnedRoomId>()
            .map_err(|_| BridgeErrorCode::InvalidArgument))
    {
        Ok(value) => value,
        Err(code) => return BridgeDataResult::failure(code),
    };
    let from = match read_optional_string(raw_from, MAX_TOKEN_LENGTH) {
        Ok(value) => value,
        Err(code) => return BridgeDataResult::failure(code),
    };
    let room = match client.get_room(&room_id) {
        Some(value) => value,
        None => return BridgeDataResult::failure(BridgeErrorCode::RoomNotFound),
    };
    let runtime = match runtime() {
        Ok(value) => value,
        Err(code) => return BridgeDataResult::failure(code),
    };
    let response = match runtime.block_on(room.messages(
        matrix_sdk::room::MessagesOptions::backward().from(from.as_deref())
    )) {
        Ok(value) => value,
        Err(_) => return BridgeDataResult::failure(BridgeErrorCode::TimelineFailed),
    };
    let events = response.chunk.into_iter().filter_map(|event| {
        serde_json::from_str::<serde_json::Value>(event.raw().json().get())
            .ok()
            .map(normalize_timeline_event)
    }).collect();
    match serde_json::to_string(&TimelinePayload { events, end: response.end }) {
        Ok(value) => BridgeDataResult::success(value),
        Err(_) => BridgeDataResult::failure(BridgeErrorCode::SerializationFailed),
    }
}

#[cfg(feature = "matrix-sdk")]
fn send_text(
    handle: u64,
    raw_room_id: *const c_char,
    raw_body: *const c_char,
    raw_transaction_id: *const c_char,
) -> BridgeDataResult {
    let client = match client_for_handle(handle) {
        Ok(value) => value,
        Err(code) => return BridgeDataResult::failure(code),
    };
    let room_id = match read_string(raw_room_id, MAX_MATRIX_ID_LENGTH)
        .and_then(|value| value.parse::<matrix_sdk::ruma::OwnedRoomId>()
            .map_err(|_| BridgeErrorCode::InvalidArgument))
    {
        Ok(value) => value,
        Err(code) => return BridgeDataResult::failure(code),
    };
    let body = match read_string(raw_body, MAX_MESSAGE_LENGTH) {
        Ok(value) => value,
        Err(code) => return BridgeDataResult::failure(code),
    };
    let transaction_id = match read_string(raw_transaction_id, MAX_MATRIX_ID_LENGTH) {
        Ok(value) => matrix_sdk::ruma::OwnedTransactionId::from(value),
        Err(code) => return BridgeDataResult::failure(code),
    };
    let room = match client.get_room(&room_id) {
        Some(value) => value,
        None => return BridgeDataResult::failure(BridgeErrorCode::RoomNotFound),
    };
    let runtime = match runtime() {
        Ok(value) => value,
        Err(code) => return BridgeDataResult::failure(code),
    };
    let encryption_unsafe = runtime.block_on(room.latest_encryption_state())
        .map_or(true, |state| state.is_encrypted() || state.is_unknown());
    if encryption_unsafe {
        return BridgeDataResult::failure(BridgeErrorCode::SendFailed);
    }
    let content = matrix_sdk::ruma::events::room::message::RoomMessageEventContent::text_plain(body);
    let response = match runtime.block_on(async {
        room.send(content).with_transaction_id(transaction_id).await
    }) {
        Ok(value) => value.response,
        Err(_) => return BridgeDataResult::failure(BridgeErrorCode::SendFailed),
    };
    match serde_json::to_string(&SendPayload { event_id: response.event_id.to_string() }) {
        Ok(value) => BridgeDataResult::success(value),
        Err(_) => BridgeDataResult::failure(BridgeErrorCode::SerializationFailed),
    }
}

#[cfg(feature = "matrix-sdk")]
fn guard_client_operation(operation: impl FnOnce() -> BridgeClientResult) -> BridgeClientResult {
    catch_unwind(AssertUnwindSafe(operation))
        .unwrap_or_else(|_| BridgeClientResult::failure(BridgeErrorCode::InternalFailure))
}

#[no_mangle]
pub extern "C" fn elementx_matrix_bridge_abi_version() -> u32 {
    ABI_VERSION
}

#[no_mangle]
pub extern "C" fn elementx_matrix_bridge_sdk_linked() -> u8 {
    u8::from(cfg!(feature = "matrix-sdk"))
}

#[no_mangle]
pub extern "C" fn elementx_matrix_bridge_runtime_ready() -> u8 {
    #[cfg(feature = "matrix-sdk")]
    {
        u8::from(catch_unwind(AssertUnwindSafe(runtime)).is_ok_and(|result| result.is_ok()))
    }
    #[cfg(not(feature = "matrix-sdk"))]
    {
        0
    }
}

#[no_mangle]
pub extern "C" fn elementx_matrix_bridge_status() -> *const c_char {
    if elementx_matrix_bridge_sdk_linked() == 0 {
        STATUS_UNAVAILABLE.as_ptr().cast()
    } else if elementx_matrix_bridge_runtime_ready() != 0 {
        STATUS_READY.as_ptr().cast()
    } else {
        STATUS_RUNTIME_UNAVAILABLE.as_ptr().cast()
    }
}

#[no_mangle]
pub extern "C" fn elementx_matrix_bridge_sdk_version() -> *const c_char {
    if elementx_matrix_bridge_sdk_linked() != 0 {
        SDK_VERSION_LINKED.as_ptr().cast()
    } else {
        SDK_VERSION_UNAVAILABLE.as_ptr().cast()
    }
}

#[no_mangle]
pub extern "C" fn elementx_matrix_bridge_error_message(error_code: u32) -> *const c_char {
    match error_code {
        value if value == BridgeErrorCode::Ok as u32 => MESSAGE_OK,
        value if value == BridgeErrorCode::InvalidArgument as u32 => MESSAGE_INVALID_ARGUMENT,
        value if value == BridgeErrorCode::InvalidHomeserverUrl as u32 => {
            MESSAGE_INVALID_HOMESERVER_URL
        }
        value if value == BridgeErrorCode::RuntimeUnavailable as u32 => MESSAGE_RUNTIME_UNAVAILABLE,
        value if value == BridgeErrorCode::ClientBuildFailed as u32 => MESSAGE_CLIENT_BUILD_FAILED,
        value if value == BridgeErrorCode::ClientNotFound as u32 => MESSAGE_CLIENT_NOT_FOUND,
        value if value == BridgeErrorCode::HandleExhausted as u32 => MESSAGE_HANDLE_EXHAUSTED,
        value if value == BridgeErrorCode::MatrixSdkUnavailable as u32 => MESSAGE_SDK_UNAVAILABLE,
        value if value == BridgeErrorCode::SessionRestoreFailed as u32 => MESSAGE_SESSION_RESTORE_FAILED,
        value if value == BridgeErrorCode::SyncFailed as u32 => MESSAGE_SYNC_FAILED,
        value if value == BridgeErrorCode::SerializationFailed as u32 => MESSAGE_SERIALIZATION_FAILED,
        value if value == BridgeErrorCode::RoomNotFound as u32 => MESSAGE_ROOM_NOT_FOUND,
        value if value == BridgeErrorCode::TimelineFailed as u32 => MESSAGE_TIMELINE_FAILED,
        value if value == BridgeErrorCode::SendFailed as u32 => MESSAGE_SEND_FAILED,
        _ => MESSAGE_INTERNAL_FAILURE,
    }
    .as_ptr()
    .cast()
}

#[no_mangle]
pub extern "C" fn elementx_matrix_bridge_create_client(
    homeserver_url: *const c_char,
) -> BridgeClientResult {
    #[cfg(feature = "matrix-sdk")]
    {
        guard_client_operation(|| create_client(homeserver_url))
    }
    #[cfg(not(feature = "matrix-sdk"))]
    {
        let _ = homeserver_url;
        BridgeClientResult::failure(BridgeErrorCode::MatrixSdkUnavailable)
    }
}

#[no_mangle]
pub extern "C" fn elementx_matrix_bridge_restore_client(
    homeserver_url: *const c_char,
    user_id: *const c_char,
    device_id: *const c_char,
    access_token: *const c_char,
    refresh_token: *const c_char,
) -> BridgeClientResult {
    #[cfg(feature = "matrix-sdk")]
    {
        guard_client_operation(|| restore_client(
            homeserver_url,
            user_id,
            device_id,
            access_token,
            refresh_token,
        ))
    }
    #[cfg(not(feature = "matrix-sdk"))]
    {
        let _ = (homeserver_url, user_id, device_id, access_token, refresh_token);
        BridgeClientResult::failure(BridgeErrorCode::MatrixSdkUnavailable)
    }
}

#[no_mangle]
pub extern "C" fn elementx_matrix_bridge_release_client(handle: u64) -> BridgeClientResult {
    #[cfg(feature = "matrix-sdk")]
    {
        guard_client_operation(|| release_client(handle))
    }
    #[cfg(not(feature = "matrix-sdk"))]
    {
        let _ = handle;
        BridgeClientResult::failure(BridgeErrorCode::MatrixSdkUnavailable)
    }
}

#[no_mangle]
pub extern "C" fn elementx_matrix_bridge_get_client_status(handle: u64) -> BridgeClientResult {
    #[cfg(feature = "matrix-sdk")]
    {
        guard_client_operation(|| client_status(handle))
    }
    #[cfg(not(feature = "matrix-sdk"))]
    {
        let _ = handle;
        BridgeClientResult::failure(BridgeErrorCode::MatrixSdkUnavailable)
    }
}

#[no_mangle]
pub extern "C" fn elementx_matrix_bridge_sync_rooms(handle: u64) -> BridgeDataResult {
    #[cfg(feature = "matrix-sdk")]
    {
        catch_unwind(AssertUnwindSafe(|| sync_rooms(handle)))
            .unwrap_or_else(|_| BridgeDataResult::failure(BridgeErrorCode::InternalFailure))
    }
    #[cfg(not(feature = "matrix-sdk"))]
    {
        let _ = handle;
        BridgeDataResult::failure(BridgeErrorCode::MatrixSdkUnavailable)
    }
}

#[no_mangle]
pub extern "C" fn elementx_matrix_bridge_load_timeline(
    handle: u64,
    room_id: *const c_char,
    from_token: *const c_char,
) -> BridgeDataResult {
    #[cfg(feature = "matrix-sdk")]
    {
        catch_unwind(AssertUnwindSafe(|| load_timeline(handle, room_id, from_token)))
            .unwrap_or_else(|_| BridgeDataResult::failure(BridgeErrorCode::InternalFailure))
    }
    #[cfg(not(feature = "matrix-sdk"))]
    {
        let _ = (handle, room_id, from_token);
        BridgeDataResult::failure(BridgeErrorCode::MatrixSdkUnavailable)
    }
}

#[no_mangle]
pub extern "C" fn elementx_matrix_bridge_send_text(
    handle: u64,
    room_id: *const c_char,
    body: *const c_char,
    transaction_id: *const c_char,
) -> BridgeDataResult {
    #[cfg(feature = "matrix-sdk")]
    {
        catch_unwind(AssertUnwindSafe(|| send_text(handle, room_id, body, transaction_id)))
            .unwrap_or_else(|_| BridgeDataResult::failure(BridgeErrorCode::InternalFailure))
    }
    #[cfg(not(feature = "matrix-sdk"))]
    {
        let _ = (handle, room_id, body, transaction_id);
        BridgeDataResult::failure(BridgeErrorCode::MatrixSdkUnavailable)
    }
}

#[no_mangle]
pub extern "C" fn elementx_matrix_bridge_free_string(value: *mut c_char) {
    if !value.is_null() {
        unsafe { drop(CString::from_raw(value)); }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[cfg(feature = "matrix-sdk")]
    use std::{
        collections::HashSet,
        ffi::CString,
        sync::{Arc, Barrier},
        thread,
    };

    #[cfg(feature = "matrix-sdk")]
    fn create(url: &str) -> BridgeClientResult {
        let url = CString::new(url).unwrap();
        elementx_matrix_bridge_create_client(url.as_ptr())
    }

    #[test]
    fn exposes_stable_bridge_status() {
        assert_eq!(elementx_matrix_bridge_abi_version(), 3);
        #[cfg(feature = "matrix-sdk")]
        {
            assert_eq!(elementx_matrix_bridge_sdk_linked(), 1);
            assert_eq!(elementx_matrix_bridge_runtime_ready(), 1);
        }
        #[cfg(not(feature = "matrix-sdk"))]
        {
            assert_eq!(elementx_matrix_bridge_sdk_linked(), 0);
            assert_eq!(elementx_matrix_bridge_runtime_ready(), 0);
        }
    }

    #[cfg(feature = "matrix-sdk")]
    #[test]
    fn rejects_invalid_homeserver_urls() {
        for value in [
            "",
            "matrix.example.org",
            "ftp://matrix.example.org",
            "https://user:secret@matrix.example.org",
            "https://matrix.example.org?token=secret",
            " https://matrix.example.org",
        ] {
            assert_eq!(create(value).error_code, BridgeErrorCode::InvalidHomeserverUrl as u32);
        }
    }

    #[cfg(feature = "matrix-sdk")]
    #[test]
    fn rejects_invalid_session_identifiers_before_restoration() {
        let url = CString::new("https://matrix.example.org").unwrap();
        let user = CString::new("alice").unwrap();
        let device = CString::new("DEVICE").unwrap();
        let token = CString::new("secret").unwrap();
        let refresh = CString::new("").unwrap();
        let result = elementx_matrix_bridge_restore_client(
            url.as_ptr(), user.as_ptr(), device.as_ptr(), token.as_ptr(), refresh.as_ptr(),
        );
        assert_eq!(result.error_code, BridgeErrorCode::InvalidArgument as u32);
    }

    #[cfg(feature = "matrix-sdk")]
    #[test]
    fn normalizes_matrix_relation_keys_for_arkts() {
        let normalized = normalize_timeline_event(serde_json::json!({
            "content": {
                "m.relates_to": {
                    "rel_type": "m.thread",
                    "m.in_reply_to": {"event_id": "$root"}
                }
            }
        }));
        assert_eq!(normalized["content"]["mRelatesTo"]["mInReplyTo"]["event_id"], "$root");
        assert!(normalized["content"].get("m.relates_to").is_none());
    }

    #[cfg(feature = "matrix-sdk")]
    #[test]
    fn manages_client_handle_lifecycle() {
        let created = create("https://matrix.example.org");
        assert_eq!(created.error_code, BridgeErrorCode::Ok as u32);
        assert_eq!(created.state, BridgeClientState::Ready as u32);
        assert_ne!(created.handle, 0);

        let status = elementx_matrix_bridge_get_client_status(created.handle);
        assert_eq!(status, created);

        let released = elementx_matrix_bridge_release_client(created.handle);
        assert_eq!(released.error_code, BridgeErrorCode::Ok as u32);
        assert_eq!(released.state, BridgeClientState::Released as u32);
        assert_eq!(released.handle, created.handle);

        let duplicate = elementx_matrix_bridge_release_client(created.handle);
        assert_eq!(duplicate.error_code, BridgeErrorCode::ClientNotFound as u32);
        let missing = elementx_matrix_bridge_get_client_status(created.handle);
        assert_eq!(missing.error_code, BridgeErrorCode::ClientNotFound as u32);
    }

    #[cfg(feature = "matrix-sdk")]
    #[test]
    fn registry_is_safe_under_concurrent_access() {
        const THREADS: usize = 8;
        let barrier = Arc::new(Barrier::new(THREADS));
        let workers: Vec<_> = (0..THREADS)
            .map(|_| {
                let barrier = Arc::clone(&barrier);
                thread::spawn(move || {
                    barrier.wait();
                    let created = create("https://matrix.example.org");
                    assert_eq!(created.error_code, BridgeErrorCode::Ok as u32);
                    assert_eq!(
                        elementx_matrix_bridge_get_client_status(created.handle).error_code,
                        BridgeErrorCode::Ok as u32
                    );
                    created.handle
                })
            })
            .collect();

        let handles: Vec<u64> = workers.into_iter().map(|worker| worker.join().unwrap()).collect();
        assert_eq!(handles.iter().copied().collect::<HashSet<_>>().len(), THREADS);
        for handle in handles {
            assert_eq!(
                elementx_matrix_bridge_release_client(handle).error_code,
                BridgeErrorCode::Ok as u32
            );
        }
    }
}
