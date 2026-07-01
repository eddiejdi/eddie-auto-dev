# Ambient TV LED MVP

Android TV / Google TV MVP to:

1. Capture the current screen with `MediaProjection`
2. Downscale the captured frames to a very small resolution
3. Compute one representative color for the whole frame
4. Smooth color changes to avoid flicker
5. Send the resulting color to a common RGB LED strip controller

This MVP is intentionally optimized for the hardware you described:

- Chromecast / Google TV as the video source
- A regular 4-pin RGB strip
- A NovaDigital / Smart Life / Tuya-compatible controller

Because the LED strip is analog RGB, the whole strip receives a single color at a time. This is mood-light, not full ambilight zoning.

## What This MVP Proves

- The capture pipeline is cheap enough when sampling at very low resolution
- The dominant/average-color algorithm is easy to run in real time
- The app architecture can separate capture, analysis, and device control cleanly
- Emulator testing is enough for the algorithm and UI loop

## What This MVP Does Not Prove

- That protected streaming apps will always expose capturable pixels
- That every Chromecast / Google TV build will allow unrestricted capture
- That your specific NovaDigital controller exposes the exact Tuya cloud DPs used here

## Project Layout

- `app/src/main/java/com/rpa4all/ambienttvled/MainActivity.kt`
  Starts and stops capture sessions and shows live state.
- `app/src/main/java/com/rpa4all/ambienttvled/capture/`
  MediaProjection, ImageReader, and service orchestration.
- `app/src/main/java/com/rpa4all/ambienttvled/color/`
  Frame sampling and color analysis.
- `app/src/main/java/com/rpa4all/ambienttvled/light/`
  LED controller abstractions, simulated mode, and Tuya cloud mode.
- `docs/`
  Setup, architecture, testing, and real-world limitations.

## Default Runtime Mode

The app starts in `SIMULATED` mode by default. That lets you validate:

- capture permission flow
- frame sampling
- color extraction
- update throttling
- UI feedback

without risking unnecessary writes to the real LED controller.

To switch to cloud control, edit `AppConfig.controllerMode`.

## Build Notes

This MVP was validated locally on this workstation with:

- Temurin JDK 21 in `/home/edenilson/.local/jdks/jdk-21.0.4+7`
- Android SDK in `/home/edenilson/Android/Sdk`
- Gradle 8.10.2

Verified command:

```bash
export JAVA_HOME=/home/edenilson/.local/jdks/jdk-21.0.4+7
export ANDROID_SDK_ROOT=/home/edenilson/Android/Sdk
export TMPDIR=/workspace/eddie-auto-dev/android/ambient-tv-led-mvp/.local-tmp
export GRADLE_USER_HOME=/workspace/eddie-auto-dev/android/ambient-tv-led-mvp/.gradle-user-home
./gradlew --no-daemon testDebugUnitTest assembleDebug
```

Generated APK:

- `app/build/outputs/apk/debug/app-debug.apk`

## Quick Start In Android Studio

1. Open this folder: `android/ambient-tv-led-mvp`
2. Let Android Studio install the Android SDK pieces it asks for
3. Run on an Android TV emulator or a Google TV device
4. Start in simulated mode
5. Confirm the color swatch changes while different content is shown
6. Only then switch to `TUYA_CLOUD`

If this machine is the target workstation, see `docs/BOOTSTRAP.md` first.

## Recommended First Test

Do not begin with Netflix or another DRM-heavy app.

Use one of these first:

- launcher UI
- local image gallery
- a simple full-screen color test app
- your own app content
