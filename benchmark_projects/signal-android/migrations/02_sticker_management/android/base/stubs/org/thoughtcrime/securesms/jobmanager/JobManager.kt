package org.thoughtcrime.securesms.jobmanager

class JobManager {
  val jobs: MutableList<Any> = mutableListOf()
  fun add(job: Any) { jobs += job }
}
