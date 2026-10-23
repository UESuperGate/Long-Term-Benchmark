package org.thoughtcrime.securesms.database

import android.database.Cursor
import org.thoughtcrime.securesms.database.model.StickerPackId
import org.thoughtcrime.securesms.database.model.StickerPackRecord
import org.thoughtcrime.securesms.database.model.StickerRecord
import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.File

class DatabaseObserver {
  fun interface Observer { fun onChanged() }
  private var stickerObserver: Observer? = null
  fun registerStickerPackObserver(observer: Observer) { stickerObserver = observer }
  fun unregisterObserver(observer: Observer) { if (stickerObserver == observer) stickerObserver = null }
  fun notifyStickerPacksChanged() { stickerObserver?.onChanged() }
}

class FixtureCursor(private val rows: List<Pair<String, String>>) : Cursor {
  private var index = -1
  override fun moveToNext(): Boolean { index += 1; return index < rows.size }
  override fun getColumnIndexOrThrow(column: String): Int = if (column == AttachmentTable.STICKER_PACK_ID) 0 else 1
  override fun getString(index: Int): String = if (index == 0) rows[this.index].first else rows[this.index].second
}

class AttachmentTable {
  var unavailable: List<Pair<String, String>> = emptyList()
  fun getUnavailableStickerPacks(): Cursor = FixtureCursor(unavailable)
  companion object {
    const val STICKER_PACK_ID = "sticker_pack_id"
    const val STICKER_PACK_KEY = "sticker_pack_key"
  }
}

class StickerTable {
  var records: MutableList<StickerPackRecord> = mutableListOf()
  val effects: MutableList<Map<String, Any?>> = mutableListOf()
  private var backingFile: File? = null

  fun resetBacking(file: File, initialRecords: List<StickerPackRecord>) {
    backingFile = file
    records = initialRecords.toMutableList()
    effects.clear()
    persist()
  }

  fun reopenBacking(): StickerTable {
    val file = checkNotNull(backingFile) { "backing store is not configured" }
    return StickerTable().also { reopened ->
      reopened.backingFile = file
      reopened.records = reopened.readRecords().toMutableList()
    }
  }

  fun getAllStickerPacks(): List<StickerPackRecord> = records.toList()
  fun deleteOrphanedPacks() { effects += mapOf("name" to "deleteOrphanedStickerPacks") }
  fun isPackAvailableAsReference(packId: String): Boolean = records.any { it.packId == packId && !it.isInstalled }
  fun markPackAsInstalled(packId: String, notify: Boolean) {
    effects += mapOf("name" to "markPackAsInstalled", "packId" to packId, "notify" to notify)
    records = records.map { if (it.packId == packId) it.copy(isInstalled = true) else it }.toMutableList()
    persist()
    org.thoughtcrime.securesms.dependencies.AppDependencies.databaseObserver.notifyStickerPacksChanged()
  }
  fun uninstallPacks(packIds: Set<StickerPackId>) {
    effects += mapOf("name" to "uninstallStickerPacks", "packIds" to packIds.map { it.value }, "count" to 1)
    records = records.map { if (packIds.any { id -> id.value == it.packId }) it.copy(isInstalled = false) else it }.toMutableList()
    persist()
    org.thoughtcrime.securesms.dependencies.AppDependencies.databaseObserver.notifyStickerPacksChanged()
  }
  fun updatePackOrder(packs: List<StickerPackRecord>) {
    effects += mapOf("name" to "setStickerPacksOrder", "packIds" to packs.map { it.packId }, "count" to 1)
    val orderedIds = packs.map { it.packId }.toSet()
    val byId = records.associateBy { it.packId }
    records = (packs.mapNotNull { byId[it.packId] } + records.filterNot { it.packId in orderedIds }).toMutableList()
    persist()
  }

  private fun persist() {
    val file = backingFile ?: return
    file.parentFile?.mkdirs()
    DataOutputStream(file.outputStream().buffered()).use { output ->
      output.writeInt(records.size)
      records.forEach { pack ->
        output.writeUTF(pack.packId)
        output.writeUTF(pack.packKey)
        output.writeUTF(pack.title)
        output.writeUTF(pack.author)
        output.writeBoolean(pack.isInstalled)
        output.writeLong(pack.cover.rowId)
        output.writeInt(pack.cover.stickerId)
        output.writeUTF(pack.cover.emoji)
        output.writeUTF(pack.cover.contentType)
        output.writeLong(pack.cover.size)
        output.writeBoolean(pack.cover.isCover)
      }
    }
  }

  private fun readRecords(): List<StickerPackRecord> {
    val file = backingFile ?: return emptyList()
    if (!file.exists()) return emptyList()
    return DataInputStream(file.inputStream().buffered()).use { input ->
      List(input.readInt()) {
        val packId = input.readUTF()
        val packKey = input.readUTF()
        val title = input.readUTF()
        val author = input.readUTF()
        val installed = input.readBoolean()
        val rowId = input.readLong()
        val stickerId = input.readInt()
        val emoji = input.readUTF()
        val contentType = input.readUTF()
        val size = input.readLong()
        val isCover = input.readBoolean()
        StickerPackRecord(packId, packKey, title, author, StickerRecord(rowId, packId, packKey, stickerId, emoji, contentType, size, isCover), installed)
      }
    }
  }

  class StickerPackRecordReader(records: List<StickerPackRecord>) : AutoCloseable {
    private val values = records
    private var index = 0
    fun asSequence(): Sequence<StickerPackRecord> = values.asSequence()
    fun getNext(): StickerPackRecord? = values.getOrNull(index++)
    override fun close() = Unit
  }
}

object SignalDatabase {
  @JvmField val stickers = StickerTable()
  @JvmField val attachments = AttachmentTable()
  @JvmStatic fun stickers(): StickerTable = stickers
  @JvmStatic fun attachments(): AttachmentTable = attachments
}
