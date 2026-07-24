# Project Status

## Project objective

The project began as an alarm intended to stop a cat from remaining in or passing through a monitored opening. It is now being consolidated into a broader **Cat Door Project** that can later include:

- reliable passage detection;
- direction detection;
- identification of the correct cat;
- motorized door locking or opening;
- local alarms;
- camera evidence;
- event history;
- remote monitoring;
- environmental sensing.

## Current active prototype

The currently deployed prototype is the cat alarm on a Raspberry Pi 2 B.

It uses:

- ADS1115 analog input channel A0;
- low and high voltage thresholds;
- a five-sample false-reset filter;
- a 30-second occupancy delay;
- an escalating buzzer pattern;
- manual button activation;
- event logging to a file and standard output;
- Raspberry Pi throttling-status logging;
- sensor-fault limits;
- a maximum continuous-buzzer cutoff.

## Current unresolved fault

The alarm unexpectedly began beeping with no visible obstruction. The retained journal showed:

- a normal-looking idle band close to 1.90 V;
- large numbers of short occupancy start/end events;
- occasional peaks around 2.7–3.2 V;
- explicit sensor faults above 3.3 V;
- eventually a continuous occupancy event exceeding 30 seconds;
- the alarm then entering its countdown exactly as programmed.

This means the software alarm was not spontaneous. The input signal told the program that the passage remained occupied. The most likely area to inspect is the sensor, its wiring, power, ground or ADS1115 input path.

## Camera subsystem

A separate security-camera application was developed for a Logitech C930e USB webcam. It includes:

- one long-running OpenCV camera owner;
- MJPEG web streaming;
- motion-triggered MP4 recording;
- webcam microphone capture;
- local audio playback experiments;
- snapshot generation;
- clip and archive management;
- Flask status and management routes.

It is preserved for later integration but should not run simultaneously with the current alarm wiring because both prototypes use GPIO17 for different purposes.

## Next immediate actions

1. Confirm the ADS1115 appears on the I²C bus.
2. Run the direct ADS test inside `catalarm-venv`.
3. Observe idle and blocked values.
4. Physically reseat the sensor wiring.
5. Determine whether high spikes are caused by a loose signal, power or ground connection.
6. Only after stable readings are restored, reconsider thresholds or software filtering.
