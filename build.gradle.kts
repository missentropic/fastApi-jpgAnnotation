plugins {
    kotlin("jvm") version "2.2.21"
    id("application")//application
    id("org.openjfx.javafxplugin") version "0.1.0"
}

group = "org.example"
version = "1.0-SNAPSHOT"



repositories {
    mavenCentral()
}

java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(21))
    }
}

application {
    mainClass.set("FileBrowserAppKt")

}

javafx {
    version = "21"
    modules = listOf("javafx.controls",
        "javafx.fxml",
        "javafx.swing")
}


dependencies {
    implementation("org.openjfx:javafx-controls:21")
    implementation("org.openjfx:javafx-fxml:21")
    implementation("com.fasterxml.jackson.core:jackson-databind:2.16.0")
    implementation("com.fasterxml.jackson.module:jackson-module-kotlin:2.16.0")
    implementation("org.openpnp:opencv:4.9.0-0")
    testImplementation(kotlin("test"))
}

kotlin {
    jvmToolchain(21)

}

tasks.test {
    useJUnitPlatform()
}