plugins {
    id("com.android.application") version "8.13.2"
    kotlin("android") version "2.1.20"
}

android {
    namespace = "org.wordpress.evaluator.support.base"
    compileSdk = 37
    defaultConfig {
        applicationId = "org.wordpress.evaluator.support.base"
        minSdk = 23
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"
        testApplicationId = "org.wordpress.evaluator.support.base.test"
        testInstrumentationRunner = "evaluator.support.instrumentation.SemanticInstrumentation"
    }
    sourceSets.getByName("main").manifest.srcFile("src/main/AndroidManifest.xml")
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
            srcDir("../evaluator/base-stubs")
            srcDir("../evaluator/base-main")
            include("org/wordpress/android/support/common/model/UserInfo.kt")
            include("org/wordpress/android/support/main/ui/SupportViewModel.kt")
            include("evaluator/supportbase/SupportBaseOwnerActivity.kt")
            include("dagger/**")
            include("javax/**")
            include("org/wordpress/android/BuildConfig.kt")
            include("org/wordpress/android/fluxc/network/NetworkRequestsRetentionPeriod.kt")
            include("org/wordpress/android/fluxc/store/AccountStore.kt")
            include("org/wordpress/android/fluxc/utils/AppLogWrapper.kt")
            include("org/wordpress/android/ui/prefs/AppPrefsWrapper.kt")
            include("org/wordpress/android/ui/prefs/experimentalfeatures/ExperimentalFeatures.kt")
            include("org/wordpress/android/util/AppLog.kt")
        }
        getByName("androidTest").kotlin.apply {
            srcDir("../evaluator/support-instrumentation")
            srcDir("../evaluator/base-runtime")
        }
    }
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.10.2")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.1")
    implementation("androidx.activity:activity-ktx:1.10.1")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.9.1")
}
