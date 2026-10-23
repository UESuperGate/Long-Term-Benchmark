plugins { id("com.android.application") version "8.13.2" }

android {
    namespace = "org.wordpress.benchmark.domains.finalapp"
    compileSdk = 37
    defaultConfig {
        applicationId = "org.wordpress.benchmark.domains.finalapp"
        minSdk = 23
        targetSdk = 37
        versionCode = 23700
        versionName = "23.7-domain-management-final"
        testApplicationId = "org.wordpress.benchmark.domains.finalapp.test"
        testInstrumentationRunner = "evaluator.domains.SemanticInstrumentation"
    }
    sourceSets.getByName("androidTest") { java.srcDirs("../evaluator/src/androidTest/java") }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
}

