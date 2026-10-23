package android.content

open class Context {
  val applicationContext: Context get() = this
  val packageName: String get() = "org.signal.benchmark"
  val packageManager: android.content.pm.PackageManager get() = android.content.pm.PackageManager()
}

class Intent(val action: String, val uri: android.net.Uri? = null) {
  fun resolveActivity(manager: android.content.pm.PackageManager): Any? = Any()
}
