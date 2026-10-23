package android.net

data class Uri private constructor(private val raw: String) {
    val path: String? get() = raw.substringAfter("://", raw)
    override fun toString(): String = raw
    companion object { fun parse(value: String): Uri = Uri(value) }
}
