# Tuya / NovaDigital Setup Notes

## Reality Check

The capture and color pipeline is deterministic.
The Tuya side is the variable part.

Before enabling cloud control, confirm:

1. The controller is visible in Tuya / Smart Life
2. You have a Tuya cloud project
3. The project is linked to the same account / device context
4. The data center region is correct
5. You know the target device ID

## Default Assumptions In This MVP

The `TuyaCloudLightController` assumes a common RGB-strip style DP set:

- `switch_led`
- `work_mode`
- `bright_value_v2`
- `colour_data_v2`

That pattern is common, but not universal.

If your controller uses different DPs, adjust:

- `TuyaCommandProfile.defaultRgbStrip()`

## Credentials Required

Edit `AppConfig.tuyaConfig` with:

- `baseUrl`
- `clientId`
- `clientSecret`
- `deviceId`
- `projectId`

## Typical Base URLs

These examples are common Tuya cloud regions:

- US: `https://openapi.tuyaus.com`
- EU: `https://openapi.tuyaeu.com`
- India: `https://openapi.tuyain.com`
- China: `https://openapi.tuyacn.com`

Choose the region that matches your Tuya project and device region.

## Safe Bring-Up Sequence

1. Run in `SIMULATED`
2. Verify capture and color output
3. Switch to `TUYA_CLOUD`
4. Send a manual test color
5. Confirm only after that the capture loop updates the real controller
