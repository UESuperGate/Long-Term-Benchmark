package org.signal.core.util.billing

enum class BillingResponseCode { OK, BILLING_UNAVAILABLE, FEATURE_NOT_SUPPORTED }
data class OneTimeProductId(val productId: String, val purchaseOptionId: String)
data class PurchaseLauncher(val id: String = "launcher")
data class OneTimeProduct(val formattedPrice: String)
sealed interface OneTimeProductResult { data class Success(val product: OneTimeProduct) : OneTimeProductResult; data object Unavailable : OneTimeProductResult; data object TransientError : OneTimeProductResult }
enum class BillingPurchaseState { PENDING, PURCHASED, UNSPECIFIED }
data class OneTimePurchase(val purchaseToken: String, val state: BillingPurchaseState = BillingPurchaseState.PURCHASED)
sealed interface OneTimePurchasePreparation {
  data class Ready(val launcher: PurchaseLauncher) : OneTimePurchasePreparation
  data class AlreadyPurchased(val purchase: OneTimePurchase) : OneTimePurchasePreparation
  data object Unavailable : OneTimePurchasePreparation
  data object NetworkError : OneTimePurchasePreparation
  data object Failed : OneTimePurchasePreparation
}
sealed interface OneTimePurchaseResult {
  data class Success(val purchase: OneTimePurchase) : OneTimePurchaseResult
  data object UserCancelled : OneTimePurchaseResult
  data object Unavailable : OneTimePurchaseResult
  data object NetworkError : OneTimePurchaseResult
  data object Failed : OneTimePurchaseResult
}
