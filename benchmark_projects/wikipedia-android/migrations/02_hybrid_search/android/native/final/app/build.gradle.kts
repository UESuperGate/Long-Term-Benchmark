plugins { id("com.android.application"); kotlin("android") }

android {
    namespace = "org.wikipedia.benchmark.hybrid.golden"
    compileSdk = 37
    defaultConfig {
        applicationId = "org.wikipedia.benchmark.hybrid.golden"
        minSdk = 23
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"
        testInstrumentationRunner = "org.wikipedia.benchmark.hybrid.native.NativeHybridInstrumentation"
    }
    sourceSets {
        getByName("main") {
            manifest.srcFile("src/main/AndroidManifest.xml")
            kotlin.srcDirs(
                "../../../final/src/upstream/kotlin",
                "../../../shared/leaf/kotlin/androidx/lifecycle",
                "../../../shared/leaf/kotlin/androidx/paging",
                "../../../shared/leaf/kotlin/kotlinx/serialization",
                "../../../shared/leaf/kotlin/org/wikipedia/dataclient",
                "../../../shared/leaf/kotlin/org/wikipedia/search",
                "../../../shared/leaf/kotlin/retrofit2/http",
                "../../../shared/native_leaf/kotlin"
            )
        }
        getByName("androidTest") { kotlin.srcDirs("../../../shared/native_test/kotlin") }
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
}

dependencies { implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.10.1") }
