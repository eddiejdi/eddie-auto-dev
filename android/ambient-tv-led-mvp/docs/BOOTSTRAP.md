# Local Bootstrap

## Current Host State

On this machine, the working Android SDK path is:

`/home/edenilson/Android/Sdk`

The bootstrap performed in this run added:

- user-local JDK 21
- user-local Gradle 8.10.2
- Android `cmdline-tools`
- Android platform `35`
- Android build-tools `35.0.0`
- generated `gradlew`

## Minimum Setup To Build

Install:

1. OpenJDK 17 or 21
2. Android Studio
3. Android SDK Platform for API 35
4. Android SDK Build-Tools
5. Android TV emulator image if you want to test locally

## First Local Fixes

1. Confirm `local.properties` points to `/home/edenilson/Android/Sdk`
2. Let Android Studio finish project sync
3. Install an Android TV emulator image if you want local UI testing
4. Keep `GRADLE_USER_HOME` on a writable disk with space

## First Validation Target

Before touching the Tuya credentials:

1. Run the app in `SIMULATED`
2. Start screen capture
3. Verify the color swatch updates
4. Verify status changes between `Capturing`, `rate limited`, and `color held`

## Verified Build Command

```bash
export JAVA_HOME=/home/edenilson/.local/jdks/jdk-21.0.4+7
export ANDROID_SDK_ROOT=/home/edenilson/Android/Sdk
export TMPDIR=/workspace/eddie-auto-dev/android/ambient-tv-led-mvp/.local-tmp
export GRADLE_USER_HOME=/workspace/eddie-auto-dev/android/ambient-tv-led-mvp/.gradle-user-home
./gradlew --no-daemon testDebugUnitTest assembleDebug
```
