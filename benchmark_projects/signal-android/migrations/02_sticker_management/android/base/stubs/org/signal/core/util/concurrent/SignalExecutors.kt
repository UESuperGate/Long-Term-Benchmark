package org.signal.core.util.concurrent

import java.util.concurrent.Executor

object SignalExecutors {
  @JvmField val SERIAL: Executor = Executor { command -> command.run() }
}
