pluginManagement { repositories { gradlePluginPortal(); mavenCentral(); google() } }
dependencyResolutionManagement {
    repositories { mavenCentral(); google() }
}
rootProject.name = "reading-challenge-native-final"
include(":app")
