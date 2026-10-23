package rs.wordpress.api.kotlin

import evaluator.support.leaf.EvaluatorLeaf
import kotlinx.coroutines.CompletableDeferred
import uniffi.wp_api.BotConversation
import uniffi.wp_api.CreateBotConversationParams
import uniffi.wp_api.ReplyToUnifiedConversationParams
import uniffi.wp_api.UnifiedConversation
import uniffi.wp_api.UnifiedConversationSummary

data class WpResponse<T>(val data: T)

sealed class WpRequestResult<out T> {
    data class Success<T>(val response: WpResponse<T>) : WpRequestResult<T>()
    data class WpError<T>(val message: String) : WpRequestResult<T>()
}

class UnifiedConversationsEndpoint {
    fun getUnifiedConversationList(): List<UnifiedConversationSummary> {
        EvaluatorLeaf.requestCount += 1
        EvaluatorLeaf.events += mapOf("name" to "loadUnifiedConversations")
        return EvaluatorLeaf.conversationList
    }
    fun getUnifiedConversation(conversationId: ULong): UnifiedConversation {
        EvaluatorLeaf.requestCount += 1
        EvaluatorLeaf.events += mapOf("name" to "loadUnifiedConversation", "conversationId" to conversationId.toLong())
        return EvaluatorLeaf.conversationDetails.getValue(conversationId.toLong())
    }
    fun replyToUnifiedConversation(conversationId: ULong, params: ReplyToUnifiedConversationParams): UnifiedConversation {
        EvaluatorLeaf.requestCount += 1
        EvaluatorLeaf.sentMessages += params.message
        EvaluatorLeaf.lastReplyAttachments = params.attachments
        EvaluatorLeaf.events += mapOf(
            "name" to "replyToUnifiedConversation",
            "conversationId" to conversationId.toLong(),
            "message" to params.message,
        )
        return EvaluatorLeaf.replyResult ?: error("reply result missing")
    }
}

class SupportBotsEndpoint {
    fun createBotConversation(botId: String, params: CreateBotConversationParams): BotConversation {
        EvaluatorLeaf.requestCount += 1
        EvaluatorLeaf.sentMessages += params.message
        EvaluatorLeaf.events += mapOf(
            "name" to "createBotConversation",
            "botId" to botId,
            "message" to params.message,
        )
        return EvaluatorLeaf.botResult ?: error("bot result missing")
    }
}

class WpRequestBuilder {
    fun unifiedConversations(): UnifiedConversationsEndpoint = UnifiedConversationsEndpoint()
    fun supportBots(): SupportBotsEndpoint = SupportBotsEndpoint()
}

open class WpComApiClient {
    open suspend fun <T> request(block: (WpRequestBuilder) -> T): WpRequestResult<T> {
        val value = try { block(WpRequestBuilder()) } catch (error: Throwable) {
            return WpRequestResult.WpError(error.message ?: "leaf_error")
        }
        EvaluatorLeaf.requestEntered.complete(Unit)
        EvaluatorLeaf.requestRelease?.await()
        return if (EvaluatorLeaf.failuresRemaining > 0) {
            EvaluatorLeaf.failuresRemaining -= 1
            WpRequestResult.WpError("controlled_failure")
        } else {
            WpRequestResult.Success(WpResponse(value))
        }
    }
}
