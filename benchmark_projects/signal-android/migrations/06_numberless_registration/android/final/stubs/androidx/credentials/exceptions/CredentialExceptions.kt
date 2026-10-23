package androidx.credentials.exceptions

open class CreateCredentialCancellationException : Exception()
open class CreateCredentialInterruptedException : Exception()
open class CreateCredentialNoCreateOptionException : Exception()
open class CreateCredentialProviderConfigurationException : Exception()
open class CreateCredentialUnknownException(message: String? = null) : Exception(message)
open class GetCredentialException : Exception()
