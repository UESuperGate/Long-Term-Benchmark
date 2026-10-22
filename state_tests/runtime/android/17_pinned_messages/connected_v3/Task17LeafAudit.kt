package runtime.task17.connected

import io.mockk.every
import io.mockk.mockk
import io.mockk.impl.JvmMockKGateway
import io.mockk.impl.stub.MockKStub
import io.mockk.impl.stub.Stub
import org.matrix.rustcomponents.sdk.TaskHandle

/** Retain even SDK errors swallowed by original runCatching. No application-owned doubles. */
class Task17LeafAudit {
    val receipts = java.util.concurrent.CopyOnWriteArrayList<Map<String, Any?>>()
    private val watched = java.util.concurrent.CopyOnWriteArrayList<Stub>()
    fun <T : Any> watch(value: T): T {
        val original = JvmMockKGateway.defaultImplementation.stubRepo.stubFor(value)
        val name = original.type.qualifiedName.orEmpty()
        check(name.startsWith("org.matrix.rustcomponents.sdk.") || name.startsWith("uniffi.")) {
            "Application-owned SDK/service/presenter doubles forbidden: $name"
        }
        check(original is MockKStub && !original.relaxed && !original.relaxUnitFun)
        watched += original
        return value
    }
    fun task(label: String, onCancel: () -> Unit = {}): TaskHandle = watch(mockk<TaskHandle>()).also { task ->
        every { task.cancel() } answers { onCancel(); receipts += mapOf("operation" to "cancel", "subscription" to label); Unit }
        every { task.destroy() } answers { receipts += mapOf("operation" to "destroy", "subscription" to label); Unit }
        every { task.close() } answers { receipts += mapOf("operation" to "close", "subscription" to label); Unit }
    }
    fun assertComplete() {
        val failures = watched.flatMap { stub ->
            val matchers = stub.matcherUsages().keys
            stub.allRecordedCalls().filter { call ->
                !call.method.isToString() && !call.method.isHashCode() && !call.method.isEquals() &&
                    matchers.none { it.match(call) }
            }.map { "${stub.type.qualifiedName}.${it.method.name}" }
        }.distinct()
        receipts += mapOf("operation" to "strict_sdk_call_audit", "unboundMethods" to failures)
        check(failures.isEmpty()) { "Original production caught unbound leaf SDK call: $failures" }
    }
}
