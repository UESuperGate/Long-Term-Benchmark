package androidx.credentials

import android.content.Context

data class CreatePasswordRequest(val id: String, val password: String, val preferImmediatelyAvailableCredentials: Boolean, val isAutoSelectAllowed: Boolean)
class GetPasswordOption
data class GetCredentialRequest(val options: List<GetPasswordOption>)
open class PasswordCredential(val id: String, val password: String)
data class GetCredentialResponse(val credential: Any)

class CredentialManager private constructor() {
  suspend fun createCredential(context: Context, request: CreatePasswordRequest) { stored = PasswordCredential(request.id, request.password) }
  suspend fun getCredential(context: Context, request: GetCredentialRequest): GetCredentialResponse = GetCredentialResponse(stored ?: throw androidx.credentials.exceptions.GetCredentialException())
  companion object {
    var stored: PasswordCredential? = null
    fun create(context: Context) = CredentialManager()
  }
}
