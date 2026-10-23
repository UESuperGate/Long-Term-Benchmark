plugins {
    id("com.android.application") version "8.13.2"
    kotlin("android") version "2.1.20"
}

android {
    namespace = "org.wordpress.evaluator.pages.base"
    compileSdk = 37
    defaultConfig {
        applicationId = "org.wordpress.evaluator.pages.base"
        minSdk = 23
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"
        testApplicationId = "org.wordpress.evaluator.pages.base.test"
        testInstrumentationRunner = "evaluator.pages.instrumentation.SemanticInstrumentation"
    }
    sourceSets {
        getByName("main") {
            manifest.srcFile("src/main/AndroidManifest.xml")
        }
    }
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
            include("org/wordpress/android/ui/pages/PagesActivity.kt")
            include("stubs/**")
            include("evaluator/pagesbase/PagesBaseOwnerActivity.kt")
        }
        getByName("androidTest").kotlin.apply {
            srcDir("../evaluator/pages-instrumentation")
            srcDir("../evaluator/base-runtime")
        }
    }
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.10.2")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.1")
    implementation("androidx.activity:activity-ktx:1.10.1")
}
