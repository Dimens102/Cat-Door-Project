import time
import board
import busio
import RPi.GPIO as GPIO

import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

BUZZER_PIN = 18
BUTTON_PIN = 17

LOW_THRESHOLD_VOLTS = 1.40
HIGH_THRESHOLD_VOLTS = 1.55
DELAY_SECONDS = 30
STATUS_EVERY_SECONDS = 60

BEEP_LENGTH = 0.07
COUNTDOWN_SECONDS = 45.0
START_INTERVAL = 5.00
END_INTERVAL = 0.08

AUTO_BUZZER_ENABLED = True

i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
chan = AnalogIn(ads, 0)

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUZZER_PIN, GPIO.OUT)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

occupied_start = None
button_start = None
last_beep_time = 0
last_status_time = 0
last_occupied = None
last_alarm = None
last_button = None
last_alarm_stage = None
false_count = 0
FALSE_RESET_COUNT = 5
occupied = False

try:
    while True:
        now = time.time()

        volts = chan.voltage
        raw_occupied = volts < LOW_THRESHOLD_VOLTS or volts > HIGH_THRESHOLD_VOLTS

        if raw_occupied:
            false_count = 0
            occupied = True
        else:
            false_count += 1
            if false_count >= FALSE_RESET_COUNT:
                occupied = False
        button_pressed = GPIO.input(BUTTON_PIN) == 0

        if occupied:
            if occupied_start is None:
                occupied_start = now
            occupied_time = now - occupied_start
            delayed_alarm = occupied_time >= DELAY_SECONDS
        else:
            occupied_start = None
            occupied_time = 0
            delayed_alarm = False

        sensor_alarm = delayed_alarm and AUTO_BUZZER_ENABLED
        alarm = sensor_alarm or button_pressed

        if button_pressed:
            alarm_stage = "button"
        elif sensor_alarm:
            alarm_stage = "sensor_alarm"
        elif delayed_alarm:
            alarm_stage = "delay_reached_no_buzzer"
        elif occupied:
            alarm_stage = "occupied_wait"
        else:
            alarm_stage = "idle"

        if button_pressed:
            if button_start is None:
                button_start = now
                last_beep_time = 0

            held_time = now - button_start

            if held_time >= COUNTDOWN_SECONDS:
                buzzer_on = True
            else:
                progress = held_time / COUNTDOWN_SECONDS
                interval = START_INTERVAL - ((START_INTERVAL - END_INTERVAL) * progress)

                if now - last_beep_time >= interval:
                    last_beep_time = now

                buzzer_on = (now - last_beep_time) < BEEP_LENGTH

        elif sensor_alarm:
            buzzer_on = True

        else:
            button_start = None
            buzzer_on = False

        if buzzer_on:
            GPIO.setup(BUZZER_PIN, GPIO.OUT)
            GPIO.output(BUZZER_PIN, 1)
        else:
            GPIO.setup(BUZZER_PIN, GPIO.OUT)
            GPIO.output(BUZZER_PIN, 0)
            GPIO.setup(BUZZER_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

        state_changed = (
            occupied != last_occupied or
            alarm != last_alarm or
            button_pressed != last_button or
            alarm_stage != last_alarm_stage
        )

        status_due = (now - last_status_time) >= STATUS_EVERY_SECONDS

        if state_changed or status_due:
            print(
                f"volts={volts:.3f} "
                f"occupied={occupied} "
                f"occupied_time={occupied_time:.1f} "
                f"button={button_pressed} "
                f"alarm={alarm} "
                f"stage={alarm_stage} "
                f"buzzer={buzzer_on} "
                f"auto_buzzer={AUTO_BUZZER_ENABLED}"
            )
            last_status_time = now
            last_occupied = occupied
            last_alarm = alarm
            last_button = button_pressed
            last_alarm_stage = alarm_stage

        time.sleep(0.2)

except KeyboardInterrupt:
    GPIO.setup(BUZZER_PIN, GPIO.OUT)
    GPIO.output(BUZZER_PIN, 0)
    GPIO.cleanup()
