plugins {
    id("com.android.application") version "8.13.2"
    kotlin("android") version "2.1.20"
    id("org.jetbrains.kotlin.plugin.compose") version "2.1.20"
}

android {
    namespace = "org.wordpress.android"
    compileSdk = 37
    defaultConfig {
        applicationId = "org.wordpress.evaluator.support.v269"
        minSdk = 23
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"
        testApplicationId = "org.wordpress.evaluator.support.v269.test"
        testInstrumentationRunner = "evaluator.support.instrumentation.SemanticInstrumentation"
    }
    sourceSets.getByName("main").manifest.srcFile("src/main/AndroidManifest.xml")
    buildFeatures { compose = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

kotlin {
    jvmToolchain(21)
    compilerOptions.jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    sourceSets {
        getByName("main").kotlin.apply {
            srcDir("upstream-immutable/WordPress/src/main/java")
            srcDir("../evaluator/final-stubs")
            srcDir("../evaluator/final-main")
            include("org/wordpress/android/support/common/model/Conversation.kt")
            include("org/wordpress/android/support/common/model/UserInfo.kt")
            include("org/wordpress/android/support/common/ui/ConversationsSupportViewModel.kt")
            include("org/wordpress/android/support/unified/model/**")
            include("org/wordpress/android/support/unified/repository/UnifiedSupportRepository.kt")
            include("org/wordpress/android/support/unified/ui/UnifiedSupportViewModel.kt")
            include("org/wordpress/android/support/unified/ui/UnifiedConversationDetailScreen.kt")
            include("org/wordpress/android/support/unified/ui/ConversationStatusBadge.kt")
            include("org/wordpress/android/support/unified/ui/SupportRuntimeOwnerActivity.kt")
            include("org/wordpress/android/support/unified/ui/PreviewStubs.kt")
            include("org/wordpress/android/support/unified/util/AttachmentStateValidator.kt")
            include("org/wordpress/android/support/unified/util/AttachmentActionsListener.kt")
            include("org/wordpress/android/support/unified/util/ConversationUtils.kt")
            include("org/wordpress/android/support/unified/util/EncryptedAppLogsUploader.kt")
            include("org/wordpress/android/support/unified/util/TempAttachmentsUtil.kt")
            include("evaluator/**")
            include("coil/**")
            include("androidx/**")
            include("dagger/**")
            include("javax/**")
            include("okhttp3/**")
            include("org/wordpress/android/**")
            include("rs/**")
            include("uniffi/**")
            exclude("android/**")
            exclude("androidx/**")
            exclude("org/wordpress/android/support/unified/ui/AttachmentFullscreenImagePreview.kt")
            exclude("org/wordpress/android/support/unified/ui/AttachmentFullscreenVideoPlayer.kt")
            exclude("org/wordpress/android/support/unified/ui/TicketMainContentView.kt")
            exclude("org/wordpress/android/support/unified/ui/UnifiedConversationsListScreen.kt")
            exclude("org/wordpress/android/support/unified/ui/UnifiedSupportActivity.kt")
        }
        getByName("androidTest").kotlin.apply {
            srcDir("../evaluator/support-instrumentation")
            srcDir("../evaluator/final-runtime")
        }
    }
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.10.2")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.1")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.9.1")
    implementation("androidx.compose.ui:ui:1.10.0")
    implementation("androidx.compose.material3:material3:1.3.2")
    implementation("androidx.compose.material:material-icons-extended:1.7.8")
}
