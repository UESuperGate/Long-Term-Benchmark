plugins { id("com.android.application") version "8.13.2"; kotlin("android") version "2.1.20"; kotlin("plugin.parcelize") version "2.1.20" }
android {
    namespace = "org.wordpress.evaluator.newstats.v276"; compileSdk = 37
    defaultConfig { applicationId = "org.wordpress.evaluator.newstats.v276"; minSdk = 23; targetSdk = 37; versionCode = 1; versionName = "1.0"; testApplicationId = "org.wordpress.evaluator.newstats.v276.test"; testInstrumentationRunner = "evaluator.newstats.instrumentation.SemanticInstrumentation" }
    sourceSets.getByName("main") { manifest.srcFile("src/main/AndroidManifest.xml"); java.srcDirs("../evaluator/final-production", "../evaluator/final-stubs", "../evaluator/final-main") }
    sourceSets.getByName("androidTest") { java.srcDirs("../evaluator/instrumentation", "../evaluator/final-runtime") }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
}
kotlin { jvmToolchain(21); compilerOptions.jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) }
dependencies { implementation("androidx.activity:activity-ktx:1.10.1"); implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.9.1"); implementation("androidx.lifecycle:lifecycle-viewmodel-savedstate:2.9.1"); implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2"); androidTestImplementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.1") }
