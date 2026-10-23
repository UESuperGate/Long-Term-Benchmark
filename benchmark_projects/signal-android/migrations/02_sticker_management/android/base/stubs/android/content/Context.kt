package android.content

import java.io.File

open class Context {
  fun getApplicationContext(): Context = this
  val filesDir: File get() = File(System.getProperty("java.io.tmpdir"), "signal-benchmark-files").also { it.mkdirs() }
}
