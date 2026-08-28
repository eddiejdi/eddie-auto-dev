# Architecture

## Goal

Produce one stable representative screen color and route it to an analog RGB strip with low CPU usage and low command noise.

## Pipeline

```text
MediaProjection
-> VirtualDisplay at low resolution
-> ImageReader frames
-> Pixel extraction
-> Edge crop + dark/bright filtering
-> Average color
-> Exponential smoothing
-> Rate limiting
-> Light controller abstraction
-> Simulated or Tuya cloud device output
```

## Why Low Resolution Is Correct Here

The LED target is a single-zone analog RGB strip.

That means:

- the strip cannot render different regions of the screen
- the app only needs one color per frame
- high-resolution capture provides little value
- low-resolution capture is the right optimization, not a compromise

The default sample grid is `64x36`, which is enough for:

- broad scene color
- low CPU usage
- minimal memory bandwidth

## Core Design Choices

### 1. Foreground service for capture lifecycle

The service owns:

- `MediaProjection`
- `VirtualDisplay`
- `ImageReader`
- coroutine processing loop
- current light controller

This avoids capture logic being tightly coupled to the activity lifecycle.

### 2. Broadcast-based state updates

The service emits simple in-app broadcasts with:

- status text
- latest color hex
- controller mode
- whether frames are flowing

This keeps the UI thin.

### 3. Pure-JVM color analyzer

The analyzer works on an `IntArray` plus width/height instead of Android `Bitmap`.

That makes the algorithm:

- easier to unit test
- easier to port
- independent of Android UI classes

### 4. Controller abstraction

`LightController` is an interface.

Current implementations:

- `SimulatedLightController`
- `TuyaCloudLightController`

This lets you prototype capture before committing to a device protocol.

## Why Tuya Cloud Is Wrapped Behind an Interface

Tuya/NovaDigital integration is the least stable part because:

- device DP codes vary
- cloud project credentials are required
- data region must match the device region

So the app keeps Tuya-specific logic isolated.

## Production Follow-Ups

If the MVP works, the next engineering upgrades should be:

1. Move configuration to an encrypted settings screen
2. Add a DP discovery helper for the target device
3. Add optional "ignore black bars" tuning presets
4. Add local control if the specific controller model supports it
5. Add a small calibration scene for saturation/brightness tuning
