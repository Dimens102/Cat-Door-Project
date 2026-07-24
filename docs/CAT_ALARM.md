# Cat Alarm Design

## Purpose

The current alarm watches one analog sensor and attempts to determine whether the monitored passage remains occupied.

## Current thresholds

```python
LOW_THRESHOLD_VOLTS = 1.35
HIGH_THRESHOLD_VOLTS = 1.90
```

A reading is considered occupied when it is:

- below the low threshold; or
- above the high threshold.

A reading outside the fault range is not accepted as valid occupancy:

```python
FAULT_LOW_VOLTS = 0.50
FAULT_HIGH_VOLTS = 3.30
```

## Occupancy filtering

The program requires five consecutive non-occupied readings before an active occupancy event ends:

```python
FALSE_RESET_COUNT = 5
```

This prevents a brief return to the idle range from immediately cancelling an event.

## Event timing

The normal occupancy delay is 30 seconds. If the sensor remains occupied for that period, the alarm begins an escalating countdown.

The sensor alarm sequence is:

1. **0–30 seconds:** occupied but silent.
2. **Next 60 seconds:** increasingly frequent short beeps.
3. **Next 60 seconds:** continuous buzzer, called the meltdown stage in the current code.
4. **After that:** forced buzzer cutoff.

The cutoff exists to prevent an indefinitely powered buzzer in the event of a stuck sensor or logic fault.

## Manual button

GPIO17 is an active-low button using the Raspberry Pi internal pull-up. The manual countdown is intentionally faster than the sensor countdown.

## Buzzer idle handling

When the buzzer is not active, GPIO18 is driven low and then changed to an input with a pull-down. This was introduced to prevent a faint residual buzz.

## Event classifications

At the end of an occupancy event, the code records one of:

- `anomaly_detected`;
- `cat_passed`;
- `cat_lingered`;
- `alarm_meltdown_reached`;
- `alarm_cutoff_reached`.

The classification is based primarily on duration.

## Known weakness

The current detection logic assumes fixed voltage bands. The recent incident showed that the sensor idle baseline can approach the high threshold and create repeated false occupancy events.

Possible future improvements include:

- startup baseline measurement;
- adaptive thresholds with bounded drift;
- median or low-pass filtering;
- explicit detection of implausible rate-of-change;
- minimum signal excursion requirement;
- separate warnings for unstable wiring;
- two-sensor corroboration.

These should only be implemented after the physical signal is stable and characterized.
