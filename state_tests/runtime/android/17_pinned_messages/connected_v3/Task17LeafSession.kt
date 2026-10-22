package runtime.task17.connected

import io.mockk.*
import org.matrix.rustcomponents.sdk.*
import kotlin.reflect.KClass
import kotlin.reflect.full.primaryConstructor

/** Non-feature FFI inputs needed by the original RustMatrixClient's real services. */
class Task17LeafSession(private val audit: Task17LeafAudit,
    private val record: (String, Map<String, Any?>) -> Unit,
    userId: String, room: Room, roomItem: RoomListItem,
) {
    val client = audit.watch(mockk<Client>())
    val sync = audit.watch(mockk<SyncService>())
    private val rooms = audit.watch(mockk<RoomListService>())
    private val encryption = audit.watch(mockk<Encryption>())
    private val verification = audit.watch(mockk<SessionVerificationController>())
    private val notifications = audit.watch(mockk<NotificationSettings>())
    private val notificationClient = audit.watch(mockk<NotificationClient>())
    private val directory = audit.watch(mockk<RoomDirectorySearch>())
    private val list = audit.watch(mockk<RoomList>())
    private val syncObservers = java.util.concurrent.CopyOnWriteArrayList<SyncServiceStateObserver>()
    init {
        every { client.userId() } returns userId
        every { client.deviceId() } returns "RUNTIME17"
        every { client.cachedAvatarUrl() } returns null
        every { client.userIdServerName() } returns "example.org"
        val sessionConstructor = checkNotNull(Session::class.primaryConstructor)
        val sessionInputs = mapOf<String, Any?>("accessToken" to "sdk-fixture-not-a-key", "refreshToken" to null,
            "userId" to userId, "deviceId" to "RUNTIME17", "homeserverUrl" to "https://example.org", "oidcData" to null,
            "slidingSyncProxy" to null)
        val sessionInput = sessionConstructor.callBy(sessionConstructor.parameters.associateWith { parameter ->
            if (sessionInputs.containsKey(parameter.name)) sessionInputs[parameter.name]
            else if (parameter.name == "slidingSyncVersion") {
                Class.forName("org.matrix.rustcomponents.sdk.SlidingSyncVersion\$Native").kotlin.objectInstance
                    ?: error("Original SDK native sync input unavailable")
            } else error("Unbound lower SDK Session input: ${parameter.name}")
        })
        every { client.session() } returns sessionInput
        every { client.encryption() } returns encryption
        every { client.getNotificationSettings() } returns notifications
        every { client.roomDirectorySearch() } returns directory
        every { client.setDelegate(any()) } answers { audit.task("client-delegate") }
        coEvery { client.notificationClient(any()) } returns notificationClient
        coEvery { client.getSessionVerificationController() } returns verification
        coEvery { client.getProfile(any()) } answers { UserProfile(firstArg<String>(), "Runtime user", null) }
        every { client.subscribeToIgnoredUsers(any()) } answers {
            firstArg<IgnoredUsersListener>().call(emptyList())
            audit.task("ignored-users")
        }
        every { client.subscribeToSendQueueStatus(any()) } answers { audit.task("send-queue") }
        coEvery { client.enableAllSendQueues(any()) } answers {
            record("sdk.Client.enableAllSendQueues", mapOf("enabled" to firstArg<Boolean>())); Unit
        }
        if (client.javaClass.methods.any { it.name == "availableSlidingSyncVersions" }) {
            val native = checkNotNull(Class.forName("org.matrix.rustcomponents.sdk.SlidingSyncVersion\$Native").kotlin.objectInstance)
            coEvery { client invoke "availableSlidingSyncVersions" withArguments emptyList() } returns listOf(native)
        }
        coEvery { client.trackRecentlyVisitedRoom(any()) } returns Unit
        every { client.destroy() } returns Unit
        every { sync.roomListService() } returns rooms
        every { sync.state(any()) } answers {
            val observer = firstArg<SyncServiceStateObserver>()
            syncObservers += observer
            observer.onUpdate(SyncServiceState.IDLE)
            audit.task("sync-state") { syncObservers.remove(observer) }
        }
        coEvery { sync.start() } answers { syncObservers.forEach { it.onUpdate(SyncServiceState.RUNNING) }; Unit }
        coEvery { sync.stop() } answers { syncObservers.forEach { it.onUpdate(SyncServiceState.IDLE) }; Unit }
        every { sync.destroy() } returns Unit
        every { encryption.backupState() } returns BackupState.ENABLED
        every { encryption.recoveryState() } returns RecoveryState.ENABLED
        every { encryption.verificationState() } returns VerificationState.VERIFIED
        every { encryption.backupStateListener(any()) } answers {
            firstArg<BackupStateListener>().onUpdate(BackupState.ENABLED)
            audit.task("backup")
        }
        every { encryption.recoveryStateListener(any()) } answers {
            firstArg<RecoveryStateListener>().onUpdate(RecoveryState.ENABLED)
            audit.task("recovery")
        }
        every { encryption.verificationStateListener(any()) } answers {
            firstArg<VerificationStateListener>().onUpdate(VerificationState.VERIFIED)
            audit.task("verification")
        }
        coEvery { encryption.waitForBackupUploadSteadyState(any()) } coAnswers {
            record("sdk.Encryption.waitForBackupUploadSteadyState", emptyMap())
            firstArg<BackupSteadyStateListener>().onUpdate(BackupUploadState.Done)
            audit.task("backup-upload-steady-state")
        }
        coEvery { encryption.isLastDevice() } returns false
        every { encryption.destroy() } returns Unit
        every { verification.setDelegate(any()) } returns Unit
        coEvery { verification.isVerified() } returns true
        every { verification.destroy() } returns Unit
        every { notifications.setDelegate(any()) } returns Unit
        coEvery { notifications.getRoomNotificationSettings(any(), any(), any()) } returns
            RoomNotificationSettings(RoomNotificationMode.ALL_MESSAGES, false)
        coEvery { notifications.getRoomsWithUserDefinedRules(any()) } returns emptyList()
        coEvery { notifications.getDefaultRoomNotificationMode(any(), any()) } returns RoomNotificationMode.ALL_MESSAGES
        every { notifications.destroy() } returns Unit
        every { notificationClient.destroy() } returns Unit
        coEvery { rooms.allRooms() } returns list
        every { rooms.room(any()) } answers {
            check(firstArg<String>() == room.id()) { "Unknown lower SDK room" }
            roomItem
        }
        every { rooms.subscribeToRooms(any(), any()) } answers {
            record("sdk.RoomListService.subscribeToRooms", mapOf("roomIds" to firstArg<List<String>>())); Unit
        }
        every { rooms.state(any()) } answers {
            firstArg<RoomListServiceStateListener>().onUpdate(RoomListServiceState.RUNNING)
            audit.task("room-list-state")
        }
        every { rooms.syncIndicator(any(), any(), any()) } answers {
            thirdArg<RoomListServiceSyncIndicatorListener>().onUpdate(RoomListServiceSyncIndicator.HIDE)
            audit.task("room-sync-indicator")
        }
        every { rooms.destroy() } returns Unit
        every { list.loadingState(any()) } answers {
            RoomListLoadingStateResult(RoomListLoadingState.Loaded(0u), audit.task("room-list-loading"))
        }
        every { list.entriesWithDynamicAdapters(any(), any()) } answers {
            secondArg<RoomListEntriesListener>().onUpdate(listOf(RoomListEntriesUpdate.Reset(emptyList())))
            entries()
        }
        every { list.destroy() } returns Unit
    }

    private fun entries(): RoomListEntriesWithDynamicAdaptersResult {
        val result = audit.watch(mockk<RoomListEntriesWithDynamicAdaptersResult>())
        val controller = audit.watch(mockk<RoomListDynamicEntriesController>())
        every { result.controller() } returns controller
        every { result.entriesStream() } answers { audit.task("room-list-entries") }
        every { result.destroy() } returns Unit
        every { controller.setFilter(any()) } returns true
        every { controller.addOnePage() } returns Unit
        every { controller.resetToOnePage() } returns Unit
        every { controller.destroy() } returns Unit
        return result
    }
}
