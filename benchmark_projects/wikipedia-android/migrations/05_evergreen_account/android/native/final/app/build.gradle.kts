plugins { id("com.android.application"); kotlin("android") }

android {
    namespace = "org.wikipedia.benchmark.evergreen.finalapp"
    compileSdk = 37
    defaultConfig {
        applicationId = "org.wikipedia.benchmark.evergreen.finalapp"
        minSdk = 37
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"
        testInstrumentationRunner = "org.wikipedia.benchmark.evergreen.native.NativeEvergreenInstrumentation"
    }
    sourceSets {
        getByName("main") { kotlin.srcDirs("src/main/kotlin") }
        getByName("androidTest") { kotlin.srcDirs("../../../shared/native_test/kotlin") }
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
}
