# Testing Guide

## Emulator First

Use an Android TV / Google TV emulator to validate:

- permission flow
- service lifecycle
- capture pipeline
- low-resolution sampling
- color smoothing
- UI state updates

### Expected Successful Emulator Result

- app starts capture
- status changes to `Capturing`
- color swatch and hex code update
- no crash when changing screens

## Real Device Second

After emulator validation:

1. Keep `SIMULATED` mode enabled
2. Install on the actual device
3. Validate whether frames arrive at all
4. Only then switch to `TUYA_CLOUD`

## Good Test Content

- flat red, green, blue screens
- bright yellow or cyan test screens
- slow scene changes
- custom test app with full-screen blocks

## Bad First Tests

- DRM-heavy apps
- content with frequent fade-to-black transitions
- noisy action scenes before tuning smoothing

## Tuning Knobs

Edit `AppConfig`:

- `sampleWidth` / `sampleHeight`
- `maxUpdatesPerSecond`
- `brightness`
- `smoothingAlpha`
- `edgeCropPercent`
- `blackThreshold`
- `whiteThreshold`

## Known Failure Modes

### 1. Black or frozen frames

Likely causes:

- protected content
- app-level secure window
- revoked capture permission

### 2. LED updates too slowly

Likely causes:

- cloud latency
- over-aggressive throttling
- too much smoothing

### 3. Wrong colors on the strip

Likely causes:

- wrong DP codes for the Tuya device
- HSV payload mismatch
- controller-specific color encoding differences
