package org.thoughtcrime.securesms.dependencies

import org.thoughtcrime.securesms.database.DatabaseObserver
import org.thoughtcrime.securesms.jobmanager.JobManager

object AppDependencies {
  @JvmField val jobManager = JobManager()
  @JvmField val databaseObserver = DatabaseObserver()
  @JvmStatic fun getJobManager(): JobManager = jobManager
  @JvmStatic fun getDatabaseObserver(): DatabaseObserver = databaseObserver
}
