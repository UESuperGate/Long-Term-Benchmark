package android.net

data class Uri(val value: String) {
  companion object {
    @JvmStatic fun parse(value: String) = Uri(value)
    @JvmStatic fun fromParts(scheme: String, ssp: String, fragment: String?) = Uri("$scheme:$ssp")
  }
}
