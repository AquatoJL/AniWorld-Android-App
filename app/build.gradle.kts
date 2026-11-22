plugins {
    alias(libs.plugins.android.application)
}

val media3Version = "1.11.1"

android {
    namespace = "com.example.aniworld"
    compileSdk {
        version = release(37)
    }

    defaultConfig {
        applicationId = "com.example.aniworld"
        minSdk = 30
        targetSdk = 37
        versionCode = 2
        versionName = "1.2.2"
    }

    buildTypes {
        release {
            optimization {
                enable = true
                packageScope = setOf("androidx.**", "kotlin.**", "kotlinx.**")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
}

dependencies {
    implementation(libs.androidx.leanback)
    implementation(libs.glide)
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("org.jsoup:jsoup:1.18.3")

    // Media3 / ExoPlayer
    implementation("androidx.media3:media3-exoplayer:$media3Version")
    implementation("androidx.media3:media3-ui:$media3Version")
    implementation("androidx.media3:media3-exoplayer-hls:$media3Version")
    implementation("androidx.media3:media3-exoplayer-dash:$media3Version")
}