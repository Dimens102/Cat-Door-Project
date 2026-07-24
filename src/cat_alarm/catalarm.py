import time
import subprocess
import board
import busio
import RPi.GPIO as GPIO

import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

BUZZER_PIN = 18
BUTTON_PIN = 17

LOW_THRESHOLD_VOLTS = 1.35
HIGH_THRESHOLD_VOLTS = 1.90
DELAY_SECONDS = 30
STATUS_EVERY_SECONDS = 60

SENSOR_BEEP_LENGTH = 0.07
SENSOR_COUNTDOWN_SECONDS = 60.0
SENSOR_START_INTERVAL = 5.00
SENSOR_END_INTERVAL = 0.12

BUTTON_BEEP_LENGTH = 0.07
BUTTON_COUNTDOWN_SECONDS = 12.0
BUTTON_START_INTERVAL = 0.80
BUTTON_END_INTERVAL = 0.06

MAX_CONTINUOUS_BUZZ_SECONDS = 60.0

AUTO_BUZZER_ENABLED = True
FALSE_RESET_COUNT = 5
ALARM_SNAPSHOT_SECONDS = 10

FAULT_LOW_VOLTS = 0.50
FAULT_HIGH_VOLTS = 3.30
SENSOR_FAULT_LOG_SECONDS = 30

LOG_FILE = "/home/beheerder/catalarm-events.log"


def get_power_status():
    try:
        result = subprocess.run(
            ["vcgencmd", "get_throttled"],
            capture_output=True,
            text=True,
            timeout=1
        )
        return result.stdout.strip()
    except Exception:
        return "power_status=unavailable"


def log_line(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    power_status = get_power_status()
    line = f"{timestamp} {message} {power_status}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
chan = AnalogIn(ads, 0)

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUZZER_PIN, GPIO.OUT)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

occupied = False
occupied_start = None
false_count = 0
raw_hits = 0
peak_volts = 0.0
low_volts = 99.0

button_start = None
last_beep_time = 0

last_status_time = 0
last_alarm_snapshot_time = 0
last_alarm_stage = None
last_sensor_fault_log = 0

logged_countdown_started = False
logged_meltdown_started = False
logged_cutoff_reached = False

log_line(
    f"SCRIPT=start "
    f"low={LOW_THRESHOLD_VOLTS:.2f} "
    f"high={HIGH_THRESHOLD_VOLTS:.2f} "
    f"delay={DELAY_SECONDS}"
)

try:
    while True:
        now = time.time()

        volts = chan.voltage
        sensor_fault = (
            volts < FAULT_LOW_VOLTS or
            volts > FAULT_HIGH_VOLTS
        )

        raw_occupied = (
            not sensor_fault and
            (volts < LOW_THRESHOLD_VOLTS or volts > HIGH_THRESHOLD_VOLTS)
        )
        if sensor_fault and (now - last_sensor_fault_log) >= SENSOR_FAULT_LOG_SECONDS:
            log_line(f"SENSOR_FAULT volts={volts:.3f}")
            last_sensor_fault_log = now
        button_pressed = GPIO.input(BUTTON_PIN) == 0

        if raw_occupied:
            false_count = 0

            if not occupied:
                occupied = True
                occupied_start = now
                raw_hits = 0
                peak_volts = volts
                low_volts = volts
                last_beep_time = 0
                last_alarm_snapshot_time = 0
                logged_countdown_started = False
                logged_meltdown_started = False
                logged_cutoff_reached = False

                log_line(
                    f"EVENT=occupancy_start "
                    f"volts={volts:.3f}"
                )

            raw_hits += 1
            peak_volts = max(peak_volts, volts)
            low_volts = min(low_volts, volts)

        else:
            false_count += 1

            if occupied and false_count >= FALSE_RESET_COUNT:
                duration = now - occupied_start if occupied_start else 0

                if duration < 1.8:
                    classification = "anomaly_detected"
                elif duration < DELAY_SECONDS:
                    classification = "cat_passed"
                elif duration < (DELAY_SECONDS + SENSOR_COUNTDOWN_SECONDS):
                    classification = "cat_lingered"
                elif duration < (DELAY_SECONDS + SENSOR_COUNTDOWN_SECONDS + MAX_CONTINUOUS_BUZZ_SECONDS):
                    classification = "alarm_meltdown_reached"
                else:
                    classification = "alarm_cutoff_reached"

                log_line(
                    f"EVENT=occupancy_end "
                    f"duration={duration:.1f} "
                    f"classification={classification} "
                    f"raw_hits={raw_hits} "
                    f"peak_volts={peak_volts:.3f} "
                    f"low_volts={low_volts:.3f}"
                )

                occupied = False
                occupied_start = None
                raw_hits = 0
                peak_volts = 0.0
                low_volts = 99.0

        occupied_time = now - occupied_start if occupied else 0

        delay_reached = occupied and occupied_time >= DELAY_SECONDS
        sensor_alarm = delay_reached and AUTO_BUZZER_ENABLED
        alarm = sensor_alarm or button_pressed

        buzzer_on = False

        if button_pressed:
            if button_start is None:
                button_start = now
                last_beep_time = 0
                log_line("BUTTON=countdown_started")

            held_time = now - button_start

            if held_time >= BUTTON_COUNTDOWN_SECONDS:
                alarm_stage = "button_continuous"
                buzzer_on = True
            else:
                alarm_stage = "button_countdown"
                progress = held_time / BUTTON_COUNTDOWN_SECONDS
                interval = BUTTON_START_INTERVAL - ((BUTTON_START_INTERVAL - BUTTON_END_INTERVAL) * progress)

                if now - last_beep_time >= interval:
                    last_beep_time = now

                buzzer_on = (now - last_beep_time) < BUTTON_BEEP_LENGTH

        elif sensor_alarm:
            button_start = None
            sensor_countdown_time = occupied_time - DELAY_SECONDS
            full_buzz_time = sensor_countdown_time - SENSOR_COUNTDOWN_SECONDS

            if full_buzz_time >= MAX_CONTINUOUS_BUZZ_SECONDS:
                alarm_stage = "sensor_alarm_cutoff"
                buzzer_on = False

                if not logged_cutoff_reached:
                    log_line(
                        f"ALARM=cutoff_reached "
                        f"occupied_time={occupied_time:.1f} "
                        f"raw_hits={raw_hits} "
                        f"peak_volts={peak_volts:.3f} "
                        f"low_volts={low_volts:.3f}"
                    )
                    logged_cutoff_reached = True

            elif sensor_countdown_time >= SENSOR_COUNTDOWN_SECONDS:
                alarm_stage = "sensor_alarm_meltdown"
                buzzer_on = True

                if not logged_meltdown_started:
                    log_line(
                        f"ALARM=meltdown_started "
                        f"occupied_time={occupied_time:.1f} "
                        f"raw_hits={raw_hits} "
                        f"peak_volts={peak_volts:.3f} "
                        f"low_volts={low_volts:.3f}"
                    )
                    logged_meltdown_started = True

            else:
                alarm_stage = "sensor_alarm_countdown"

                if not logged_countdown_started:
                    log_line(
                        f"ALARM=countdown_started "
                        f"occupied_time={occupied_time:.1f} "
                        f"raw_hits={raw_hits} "
                        f"peak_volts={peak_volts:.3f} "
                        f"low_volts={low_volts:.3f}"
                    )
                    logged_countdown_started = True

                progress = sensor_countdown_time / SENSOR_COUNTDOWN_SECONDS
                interval = SENSOR_START_INTERVAL - ((SENSOR_START_INTERVAL - SENSOR_END_INTERVAL) * progress)

                if now - last_beep_time >= interval:
                    last_beep_time = now

                buzzer_on = (now - last_beep_time) < SENSOR_BEEP_LENGTH

            if now - last_alarm_snapshot_time >= ALARM_SNAPSHOT_SECONDS:
                log_line(
                    f"ALARM=snapshot "
                    f"stage={alarm_stage} "
                    f"occupied_time={occupied_time:.1f} "
                    f"raw_hits={raw_hits} "
                    f"volts={volts:.3f} "
                    f"buzzer={buzzer_on}"
                )
                last_alarm_snapshot_time = now

        else:
            if button_start is not None:
                log_line("BUTTON=released")

            button_start = None

            if delay_reached:
                alarm_stage = "delay_reached_no_buzzer"
            elif occupied:
                alarm_stage = "occupied_wait"
            else:
                alarm_stage = "idle"
                last_beep_time = 0

        if buzzer_on:
            GPIO.setup(BUZZER_PIN, GPIO.OUT)
            GPIO.output(BUZZER_PIN, 1)
        else:
            GPIO.setup(BUZZER_PIN, GPIO.OUT)
            GPIO.output(BUZZER_PIN, 0)
            GPIO.setup(BUZZER_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

        if alarm_stage != last_alarm_stage:
            print(
                f"volts={volts:.3f} "
                f"occupied={occupied} "
                f"occupied_time={occupied_time:.1f} "
                f"raw_hits={raw_hits} "
                f"button={button_pressed} "
                f"alarm={alarm} "
                f"stage={alarm_stage} "
                f"buzzer={buzzer_on} "
                f"auto_buzzer={AUTO_BUZZER_ENABLED}"
            )
            last_alarm_stage = alarm_stage

        if now - last_status_time >= STATUS_EVERY_SECONDS:
            print(
                f"volts={volts:.3f} "
                f"occupied={occupied} "
                f"occupied_time={occupied_time:.1f} "
                f"raw_hits={raw_hits} "
                f"button={button_pressed} "
                f"alarm={alarm} "
                f"stage={alarm_stage} "
                f"buzzer={buzzer_on} "
                f"auto_buzzer={AUTO_BUZZER_ENABLED}"
            )
            last_status_time = now

        time.sleep(0.2)

except KeyboardInterrupt:
    log_line("SCRIPT=keyboard_interrupt")
    GPIO.setup(BUZZER_PIN, GPIO.OUT)
    GPIO.output(BUZZER_PIN, 0)
    GPIO.cleanup()

except Exception as e:
    log_line(f"SCRIPT=crash error={repr(e)}")
    GPIO.setup(BUZZER_PIN, GPIO.OUT)
    GPIO.output(BUZZER_PIN, 0)
    GPIO.cleanup()
    raise
