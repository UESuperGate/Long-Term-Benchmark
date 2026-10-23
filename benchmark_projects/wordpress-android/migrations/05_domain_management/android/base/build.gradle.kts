plugins { id("com.android.application") version "8.13.2" }

android {
    namespace = "org.wordpress.benchmark.domains.base"
    compileSdk = 37
    defaultConfig {
        applicationId = "org.wordpress.benchmark.domains.base"
        minSdk = 23
        targetSdk = 37
        versionCode = 23600
        versionName = "23.6-domain-management-base"
        testApplicationId = "org.wordpress.benchmark.domains.base.test"
        testInstrumentationRunner = "evaluator.domains.SemanticInstrumentation"
    }
    sourceSets.getByName("androidTest") { java.srcDirs("../evaluator/src/androidTest/java") }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
}

