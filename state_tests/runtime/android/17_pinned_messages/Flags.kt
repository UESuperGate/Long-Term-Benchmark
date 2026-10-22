package io.element.android.libraries.featureflag.api
import kotlinx.coroutines.flow.MutableStateFlow
enum class FeatureFlags { PinnedEvents }
class FeatureFlagService { fun isFeatureEnabledFlow(flag: FeatureFlags) = MutableStateFlow(true) }
