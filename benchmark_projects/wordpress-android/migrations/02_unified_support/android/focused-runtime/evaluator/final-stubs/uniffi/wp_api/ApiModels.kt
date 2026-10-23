package uniffi.wp_api

import java.util.Date

data class CreateBotConversationParams(val message: String, val userId: Long)
data class ReplyToUnifiedConversationParams(
    val message: String,
    val attachments: List<String>,
    val encryptedLogIds: List<String>,
)

sealed interface JsonValue {
    data class Float(val v1: Double) : JsonValue
    data class Int(val v1: Long) : JsonValue
    data class String(val v1: kotlin.String) : JsonValue
}

data class UnifiedConversationSummary(
    val id: ULong,
    val title: String,
    val description: String,
    val status: String,
    val canAcceptReply: Boolean,
    val createdAt: Date,
    val updatedAt: Date,
)

data class UnifiedAttachment(
    val id: ULong,
    val filename: String,
    val contentType: String,
    val url: String,
    val metadata: Map<String, JsonValue> = emptyMap(),
)

data class UnifiedMessage(
    val id: ULong,
    val message: String,
    val authorRole: String,
    val authorName: String,
    val createdAt: Date,
    val attachments: List<UnifiedAttachment> = emptyList(),
) {
    // WordPress 26.9 names this payload `message`; compatible candidates may expose `content`.
    val content: String get() = message
}

data class UnifiedConversation(
    val id: ULong,
    val title: String,
    val description: String,
    val status: String,
    val canAcceptReply: Boolean,
    val createdAt: Date,
    val updatedAt: Date,
    val messages: List<UnifiedMessage>,
)

data class BotMessage(
    val messageId: ULong,
    val content: String,
    val role: String,
    val createdAt: Date,
)

data class BotConversation(
    val chatId: ULong,
    val createdAt: Date,
    val messages: List<BotMessage>,
)
