plugins { id("com.android.application"); kotlin("android") }

android {
    namespace = "org.wikipedia.benchmark.explore.golden"
    compileSdk = 37
    defaultConfig {
        applicationId = "org.wikipedia.benchmark.explore.golden"
        minSdk = 23
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"
        testInstrumentationRunner = "org.wikipedia.benchmark.explore.native.NativeExploreInstrumentation"
    }
    sourceSets {
        getByName("main") {
            manifest.srcFile("src/main/AndroidManifest.xml")
            kotlin.srcDirs("src/main/upstream/kotlin")
        }
        getByName("androidTest") { kotlin.srcDirs("../../../shared/native_test/kotlin") }
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
}

