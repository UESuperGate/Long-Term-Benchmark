plugins { id("com.android.application"); kotlin("android") }

android {
    namespace = "org.wikipedia.benchmark.saved.base"
    compileSdk = 37
    defaultConfig {
        applicationId = "org.wikipedia.benchmark.saved.base"
        minSdk = 23
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"
        testInstrumentationRunner = "org.wikipedia.benchmark.saved.native.NativeSavedInstrumentation"
    }
    sourceSets {
        getByName("main") {
            manifest.srcFile("src/main/AndroidManifest.xml")
            kotlin.srcDirs("src/main/upstream/kotlin", "src/main/java")
        }
        getByName("androidTest") { kotlin.srcDirs("../../../shared/native_test/kotlin") }
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
}

