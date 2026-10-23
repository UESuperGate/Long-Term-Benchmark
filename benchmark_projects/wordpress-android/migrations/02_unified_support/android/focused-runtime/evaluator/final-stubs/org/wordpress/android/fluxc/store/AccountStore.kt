package org.wordpress.android.fluxc.store

data class AccountModel(
    var displayName: String = "Ada",
    var userName: String = "ada",
    var email: String = "ada@example.test",
    var avatarUrl: String = "",
    var userId: Long = 42,
)

open class AccountStore {
    open var accessToken: String = "token"
    open var account: AccountModel = AccountModel()
    open fun hasAccessToken(): Boolean = accessToken.isNotEmpty()
}
