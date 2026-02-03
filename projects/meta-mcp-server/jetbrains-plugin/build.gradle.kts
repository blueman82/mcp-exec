plugins {
    id("java")
    id("org.jetbrains.kotlin.jvm") version "1.9.25"
    id("org.jetbrains.intellij.platform") version "2.2.1"
    id("org.jetbrains.kotlin.plugin.serialization") version "1.9.25"
}

group = "com.adobe.metamcp"
version = "1.0.0"

repositories {
    mavenCentral()
    intellijPlatform {
        defaultRepositories()
    }
}

// Enable automatic JDK download
@Suppress("UnstableApiUsage")
java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(17))
        vendor.set(JvmVendorSpec.JETBRAINS)
    }
}

dependencies {
    intellijPlatform {
        intellijIdeaCommunity("2024.1")
        bundledPlugin("com.intellij.java")
    }

    // Kotlin serialization for JSON
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")

    // Ktor client for HTTP requests (GitHub API)
    implementation("io.ktor:ktor-client-core:2.3.12")
    implementation("io.ktor:ktor-client-cio:2.3.12")
    implementation("io.ktor:ktor-client-content-negotiation:2.3.12")
    implementation("io.ktor:ktor-serialization-kotlinx-json:2.3.12")

    // Coroutines - provided by IntelliJ Platform, only needed for compile
    compileOnly("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.8.1")

    // Testing
    testImplementation("org.jetbrains.kotlin:kotlin-test")
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.0")
}

kotlin {
    jvmToolchain(17)
}

intellijPlatform {
    pluginConfiguration {
        name = "Meta-MCP"
        ideaVersion {
            sinceBuild = "241"
            untilBuild = "253.*"
        }
    }

    signing {
        // Configure signing if needed for marketplace
    }

    publishing {
        // Configure publishing to JetBrains Marketplace if needed
    }
}

tasks {
    test {
        useJUnitPlatform()
    }

    // Include dependencies in plugin distribution
    prepareSandbox {
        duplicatesStrategy = DuplicatesStrategy.EXCLUDE
        from(configurations.runtimeClasspath.get().filter {
            it.name.contains("ktor") ||
            it.name.contains("kotlinx-serialization")
        }) {
            into("${intellijPlatform.projectName.get()}/lib")
        }
    }
}
