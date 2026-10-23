plugins {
    kotlin("jvm") version "2.1.20"
}

repositories { mavenCentral() }

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.10.1")
}

kotlin { jvmToolchain(17) }

sourceSets {
    main {
        kotlin.setSrcDirs(listOf("src/upstream/kotlin", "../shared/leaf/kotlin"))
        java.setSrcDirs(emptyList<String>())
    }
}

tasks.register("writeRuntimeClasspath") {
    dependsOn(tasks.named("classes"))
    doLast {
        layout.buildDirectory.file("runtime-classpath.txt").get().asFile.writeText(
            sourceSets.main.get().runtimeClasspath.asPath
        )
    }
}
