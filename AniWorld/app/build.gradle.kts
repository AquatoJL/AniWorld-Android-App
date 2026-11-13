plugins {
    alias(libs.plugins.android.application)
}

android {
    namespace = "com.example.aniworld"
    compileSdk {
        version = release(35)
    }

    defaultConfig {
        applicationId = "com.example.aniworld"
        minSdk = 35
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"

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
}