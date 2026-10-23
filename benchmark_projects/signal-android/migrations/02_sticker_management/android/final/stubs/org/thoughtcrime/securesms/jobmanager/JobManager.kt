package org.thoughtcrime.securesms.jobmanager

class JobManager {
  val jobs: MutableList<Any> = mutableListOf()
  var beforeAdd: ((Any) -> Unit)? = null

  fun add(job: Any) {
    beforeAdd?.invoke(job)
    jobs += job
    if (job is org.thoughtcrime.securesms.jobs.StickerPackDownloadJob && job.kind == "INSTALL") RuntimeTrace.events += "EFFECT:installStickerPack"
  }
}

object RuntimeTrace {
  val events: MutableList<String> = mutableListOf()
}
