plugins {
    id("com.android.application") version "8.13.2"
    kotlin("android") version "2.1.20"
}

android {
    namespace = "org.wordpress.evaluator.pages.v269"
    compileSdk = 37
    defaultConfig {
        applicationId = "org.wordpress.evaluator.pages.v269"
        minSdk = 23
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"
        testApplicationId = "org.wordpress.evaluator.pages.v269.test"
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
            srcDir("../evaluator/final-stubs")
            srcDir("../evaluator/final-main")
            include("org/wordpress/android/ui/pagesrs/PageRsFluxCBridge.kt")
            include("org/wordpress/android/ui/pagesrs/PageRsHomepageSettings.kt")
            include("org/wordpress/android/ui/pagesrs/PageRsListEvent.kt")
            include("org/wordpress/android/ui/pagesrs/PageRsListTab.kt")
            include("org/wordpress/android/ui/pagesrs/PageRsListUiState.kt")
            include("org/wordpress/android/ui/pagesrs/PageRsMenuActions.kt")
            include("org/wordpress/android/ui/pagesrs/PageRsTreeBuilder.kt")
            include("org/wordpress/android/ui/pagesrs/PagesRsListViewModel.kt")
            include("org/wordpress/android/ui/pagesrs/PagesRuntimeOwnerActivity.kt")
            include("android/**")
            include("androidx/**")
            include("dagger/**")
            include("javax/**")
            include("org/greenrobot/**")
            include("org/wordpress/android/**")
            include("rs/**")
            include("uniffi/**")
            exclude("androidx/**")
            exclude("org/wordpress/android/ui/pagesrs/PagesRsListActivity.kt")
            exclude("org/wordpress/android/ui/pagesrs/screens/**")
        }
        getByName("androidTest").kotlin.apply {
            srcDir("../evaluator/pages-instrumentation")
            srcDir("../evaluator/final-runtime")
        }
    }
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.10.2")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.1")
    implementation("androidx.activity:activity-ktx:1.10.1")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.9.1")
}

tasks.withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompile>().configureEach {
    compilerOptions.freeCompilerArgs.add("-Xconsistent-data-class-copy-visibility")
}
