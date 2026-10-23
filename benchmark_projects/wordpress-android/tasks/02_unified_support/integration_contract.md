# Unified Support Integration Contract

This document defines the production API surface used by the runtime integration. Implementations may organize private helpers differently, but the symbols below must remain available with compatible signatures.

## Android production surface

- Target package: `org.wordpress.android.support.unified`
- Target source path: `WordPress/src/main/java/org/wordpress/android/support/unified/`
- Shared production dependencies compiled with the target are `WordPress/src/main/java/org/wordpress/android/support/common/model/Conversation.kt` and `WordPress/src/main/java/org/wordpress/android/support/common/ui/ConversationsSupportViewModel.kt`.
- Candidate production sources are discovered by the target package or path. Test-source or evaluator-owned APIs are not part of the implementation contract.

The main APK owns a `SupportRuntimeOwnerActivity`. Instrumentation launches that entry and dispatches
all events through owner methods. The owner acquires `UnifiedSupportViewModel` from its
`ViewModelStore` with `ViewModelProvider`; the evaluator does not construct or drive a detached
presenter.

The owner dependency factory constructs these production classes:

```kotlin
class UnifiedSupportRepository(
    appLogWrapper: AppLogWrapper,
    wpComApiClientProvider: WpComApiClientProvider,
    ioDispatcher: CoroutineDispatcher,
)

class TempAttachmentsUtil(
    ioDispatcher: CoroutineDispatcher,
    okHttpClient: OkHttpClient,
    appLogWrapper: AppLogWrapper,
    application: Application,
    accountStore: AccountStore,
)

class AttachmentStateValidator(
    application: Application,
    ioDispatcher: CoroutineDispatcher,
)

class EncryptedAppLogsUploader(
    encryptedLogging: EncryptedLogging,
    logFileProvider: LogFileProviderWrapper,
    appLogWrapper: AppLogWrapper,
    ioDispatcher: CoroutineDispatcher,
)

class UnifiedSupportViewModel(
    accountStore: AccountStore,
    repository: UnifiedSupportRepository,
    tempAttachmentsUtil: TempAttachmentsUtil,
    attachmentStateValidator: AttachmentStateValidator,
    encryptedAppLogsUploader: EncryptedAppLogsUploader,
    ioDispatcher: CoroutineDispatcher,
    appLogWrapper: AppLogWrapper,
    networkUtilsWrapper: NetworkUtilsWrapper,
)
```

The application owner exposes these evaluator-facing event methods:

```kotlin
fun SupportRuntimeOwnerActivity.retryConversations()
fun SupportRuntimeOwnerActivity.openConversation(id: Long)
fun SupportRuntimeOwnerActivity.createBotConversation()
fun SupportRuntimeOwnerActivity.updateReplyMessage(message: String)
fun SupportRuntimeOwnerActivity.addReplyAttachments(uris: List<Uri>)
fun SupportRuntimeOwnerActivity.updateReplyIncludeAppLogs(include: Boolean)
fun SupportRuntimeOwnerActivity.updateReplySheetVisibility(visible: Boolean)
fun SupportRuntimeOwnerActivity.sendReply(message: String, includeAppLogs: Boolean = false)
fun SupportRuntimeOwnerActivity.renderSelectedDetail()
```

Those owner methods invoke these production methods:

```kotlin
fun UnifiedSupportRepository.init(accessToken: String, userId: Long)
suspend fun UnifiedSupportRepository.loadConversations(): List<UnifiedConversation>?
suspend fun UnifiedSupportRepository.loadConversation(conversationId: Long): UnifiedConversation?
suspend fun UnifiedSupportRepository.createNewBotConversation(message: String): UnifiedConversation?
suspend fun UnifiedSupportRepository.replyToConversation(
    conversationId: Long,
    message: String,
    attachments: List<String> = emptyList(),
    encryptedLogIds: List<String> = emptyList(),
): UnifiedConversation?

fun UnifiedSupportViewModel.init()
fun UnifiedSupportViewModel.refreshConversations()
fun UnifiedSupportViewModel.clearError()
fun UnifiedSupportViewModel.onConversationClick(conversation: UnifiedConversation)
fun UnifiedSupportViewModel.onCreateNewBotConversationClick()
fun UnifiedSupportViewModel.sendReply(message: String, includeAppLogs: Boolean = false)
fun UnifiedSupportViewModel.addReplyAttachments(uris: List<Uri>)
fun UnifiedSupportViewModel.updateReplyMessage(message: String)
fun UnifiedSupportViewModel.updateReplyIncludeAppLogs(include: Boolean)
fun UnifiedSupportViewModel.updateReplyBottomSheetVisibility(isVisible: Boolean)

```

The runtime observes only production state, production Compose accessibility semantics, and
controlled-leaf call logs:

```kotlin
val conversations: StateFlow<List<UnifiedConversation>>
val selectedConversation: StateFlow<UnifiedConversation?>
val isLoadingConversation: StateFlow<Boolean>
val conversationsState: StateFlow<ConversationsSupportViewModel.ConversationsState>
val errorMessage: StateFlow<ConversationsSupportViewModel.ErrorType?>
val isSendingReply: StateFlow<Boolean>
val replyFormState: StateFlow<ConversationReplyFormState>
```

The following production model constructors and readable properties are used:

```kotlin
data class UnifiedConversation(
    val id: Long,
    val title: String,
    val description: String,
    val status: String,
    val canAcceptReply: Boolean,
    val createdAt: Date,
    val updatedAt: Date,
    val messages: List<UnifiedMessage>,
) : Conversation

data class UnifiedMessage(
    val id: Long,
    val formattedText: AnnotatedString,
    val authorRole: String,
    val authorName: String,
    val createdAt: Date,
    val attachments: List<UnifiedAttachment>,
)

data class ConversationReplyFormState(
    val message: String = "",
    val includeAppLogs: Boolean = false,
    val attachmentState: AttachmentState = AttachmentState(),
    val isBottomSheetVisible: Boolean = false,
)
```

`UnifiedConversation.getConversationId()`, `UnifiedConversation.isBot`, `UnifiedMessage.isUser`, and the readable fields of `AttachmentState` are also part of the runtime-facing production surface.

The `detail_affordances` case renders the upstream `UnifiedConversationDetailScreen` and reads its
API37 accessibility tree. The evaluator must not reproduce `ConversationBottomBar` branching or use
`ConversationStatus.fromStatus` to synthesize a verdict. The `draft_lifecycle` case calls the real
`Activity.recreate()`, waits for a replacement owner, proves `ViewModel` identity retention, and then
opens conversation 10 through the production repository path.

## Android leaf boundaries

The runtime controls external outcomes beneath the production repository and utilities. Production code continues to call the normal leaves:

```kotlin
fun NetworkUtilsWrapper.isNetworkAvailable(): Boolean

fun WpComApiClientProvider.getWpComApiClient(accessToken: String): WpComApiClient
// WpComApiClient request builders expose:
// unifiedConversations().getUnifiedConversationList()
// unifiedConversations().getUnifiedConversation(conversationId)
// supportBots().createBotConversation(botId, params)
// unifiedConversations().replyToUnifiedConversation(conversationId, params)

suspend fun AttachmentStateValidator.addAttachments(
    currentAttachmentState: AttachmentState,
    uris: List<Uri>,
): AttachmentState
suspend fun AttachmentStateValidator.removeAttachment(
    currentState: AttachmentState,
    uri: Uri,
): AttachmentState

suspend fun TempAttachmentsUtil.createTempFilesFrom(uris: List<Uri>): List<File>
suspend fun TempAttachmentsUtil.removeTempFiles(files: List<File>)
suspend fun EncryptedAppLogsUploader.uploadLogs(): List<String>
```

The utility implementations use the Android `Application` content resolver, `LogFileProviderWrapper.getLogFiles()`, and `EncryptedLogging.encryptAndUploadLogFile(...)` as their external I/O leaves. No evaluator-specific interface is required in production code.

`given` may configure API responses, network availability, content-provider bytes and MIME metadata,
log files, and held request completion. Derived list/detail/reply-form state must be established through
the owner and production ViewModel; direct `setNewConversation` or state-flow writes are forbidden.

The arbitrary-candidate harness always enters an application-owned Activity. An untouched 26.8
candidate executes the shared `SupportViewModel.init()` prefix through a retained owner ViewModel and
is scored from that runtime observation; source discovery and adapter wiring metadata never determine
a case verdict. Missing instrumentation, missing runtime symbols, process crashes, invalid payloads,
and install failures are infrastructure errors and remain `not_scored`, never semantic failures.

## ArkTS controller surface

- Production source path: `entry/src/main/ets/features/UnifiedSupportController.ets`
- The device runtime imports the following exports from that module.

```typescript
export interface SupportMessage {
  id: number;
  author: string;
  text: string;
}

export interface SupportConversation {
  id: number;
  title: string;
  status: string;
  canAcceptReply: boolean;
  messages: SupportMessage[];
}

export interface SupportServiceLeaf {
  loadConversations(): Promise<SupportConversation[]>;
  loadConversation(id: number): Promise<SupportConversation>;
  createBotConversation(botId: string, message: string): Promise<SupportConversation>;
  reply(
    id: number,
    message: string,
    attachments: string[],
    logIds: string[],
  ): Promise<SupportConversation>;
}

export interface NetworkLeaf {
  online(): boolean;
}

export interface AttachmentLeaf {
  uploadEncryptedLogs(): Promise<string[]>;
  createTempFiles(inputs: string[]): Promise<string[]>;
  removeTempFiles(paths: string[]): Promise<void>;
}

export interface DetailAffordance {
  composer: string;
  typingIndicatorSupported: boolean;
  closedBanner: boolean;
}
```

`UnifiedSupportController` is constructed as:

```typescript
new UnifiedSupportController(
  service: SupportServiceLeaf,
  network?: NetworkLeaf,
  attachments?: AttachmentLeaf,
)
```

It exposes a readable `store: UnifiedSupportStore`. The runtime calls:

```typescript
open(): Promise<boolean>;
retry(): Promise<boolean>;
openConversation(id: number): Promise<boolean>;
createNewBotConversation(): void;
updateDraft(message: string): void;
updateAttachments(values: string[]): void;
setIncludeAppLogs(value: boolean): void;
setReplySheetVisible(value: boolean): void;
detailState(conversation: SupportConversation): DetailAffordance;
detailAffordance(conversation: SupportConversation): string;
sendReply(message: string): Promise<boolean>;
```

The readable `UnifiedSupportStore` and reply-form state are:

```typescript
surface: string;
entryLabel: string;
conversations: SupportConversation[];
selected?: SupportConversation;
replyForm: ReplyFormState;
loading: boolean;
sending: boolean;
error: string;
requestCount: number;

// ReplyFormState
message: string;
attachments: string[];
includeAppLogs: boolean;
sheetVisible: boolean;
clear(): void;
```
