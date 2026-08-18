# Status, error codes, and how to tell a stale reading

## The one that matters: is the value fresh?

**Use `measureErrorCode` (register 1004). Do not use `ok` (register 1029).**

This trips people up often enough to deserve the top of the page. `ok` reports
*sampling quality for this cycle*. On aerated or turbulent slurry it is
routinely 0 while the process value is perfectly fresh and the 4–20 mA loop is
completely normal. Code that treats `ok == 0` as "the value is frozen" will
silently stop acting on threshold alarms exactly when the process gets noisy —
which is when you need them.

A value is stale — meaning the instrument returned early this cycle and
`mainValueFiltered` still holds the previous frame — when any of these bits are
set in `measureErrorCode`:

| Bit | Name |
|---:|---|
| 0 | NOT_ENOUGH_MEMORY |
| 1 | NOT_ENOUGH_DATA |
| 3 | CALIBRATION_DATA_INVALID |
| 4 | CALIBRATION_FAILURE |
| 6 | FAILED |

When any of those are set the current loop has also dropped to its NAMUR NE43
alarm level, so the analogue and digital paths agree.

## measureErrorCode — register 1004

| Bit | Name | Means |
|---:|---|---|
| 0 | NOT_ENOUGH_MEMORY | Buffer allocation failed. **Value stale.** |
| 1 | NOT_ENOUGH_DATA | Too few valid frames to average. **Value stale.** |
| 2 | SENSOR_TEMPERATURE_INVALID | Probe PT1000 fault. Value still published, but temperature compensation is degraded — check wiring to the probe. |
| 3 | CALIBRATION_DATA_INVALID | Active calibration set is not usable. **Value stale.** |
| 4 | CALIBRATION_FAILURE | Lookup against the calibration table failed, usually because the process moved outside the calibrated range. **Value stale.** |
| 5 | FLUCTUATION | Reading is noisy beyond the configured limit. Value is live — treat as a quality hint, not a fault. |
| 6 | FAILED | Measurement cycle failed. **Value stale.** |
| 7 | SOLUBILITY_CALIBRATION_DATA_INVALID | Solubility table not usable. |

## systemErrorCode — register 1005

| Bit | Name | Means |
|---:|---|---|
| 0 | AD5420_WRITE_FAIL | Could not write the current-loop DAC |
| 1 | AD5420_WRITE_NOT_CORRECT | DAC readback did not match what was written |

Either bit means the 4–20 mA output cannot be trusted. The Modbus value is
unaffected.

## moduleStatus — registers 1000–1001 (U32)

One bit per subsystem, set when that subsystem initialised or is active.

| Bit | Name |
|---:|---|
| 0 | WATCHDOG_RESET |
| 1 | MEASURE_INIT |
| 2 | MODBUS_INIT |
| 3 | SYSTEM_INIT |
| 4 | HISTORY_INIT |
| 5 | RTC_INIT |
| 6 | ONBOARD_TEMP_SENSOR_INIT |
| 7 | AD5420_INIT |
| 8 | GAIN_INIT |
| 9 | LCD_INIT |
| 10 | AD5420_CH1 |
| 11 | AD5420_CH2 |
| 12 | PT1000_TEMP_REMEDIATION |
| 13 | CLEANER_RUNNING |

Bit 0 set after an unexpected restart is worth logging — pair it with
`upTime` (register 1074) to catch a device that is silently rebooting.

## Unit codes — registers 1023 and 1028

| Code | Quantity | Unit |
|---:|---|---|
| 0 | Density | g/cm³ |
| 1 | Volume concentration | % |
| 2 | Mass concentration | % |
| 3 | Baumé | °Bé |
| 4 | Solids concentration | g/L |
| 5 | Density | kg/m³ |

**Always read the unit code alongside the value.** The same instrument can be
configured to report density or concentration, and a host that assumes one
will be wrong by a factor of roughly 100 when someone changes it on the panel.

## Output type — registers 1039 and 1050

| Code | Loop carries |
|---:|---|
| 0 | Main value |
| 1 | Temperature |
| 2 | Energy |

## currentMode — register 1037

Non-zero means the instrument is in current-loop calibration mode: the 4–20 mA
output is pinned to a fixed test value and is **not** following the process.
A host that trends the analogue signal should mark this period rather than
recording it as real data.

## Entrained gas — registers 1104 and 1113

Available on SW 4.x. `gasIndex` (1104) is the instantaneous index, 0–100, and
`gasIndexEma` (1113) is its smoothed form.

Alarm on the smoothed value. The instantaneous one spikes when a single bubble
crosses the beam, while that particular measurement is usually still fine.

The index is derived from frame-to-frame variance rather than absolute echo
amplitude. That distinction is the point of it: absolute amplitude cannot
separate "more bubbles" from "more solids", because both push the amplitude
the same way. Variance can.
