import time
import board
import busio
import RPi.GPIO as GPIO

import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

BUZZER_PIN = 18
BUTTON_PIN = 17

LOW_THRESHOLD_VOLTS = 1.40
HIGH_THRESHOLD_VOLTS = 1.60
DELAY_SECONDS = 10
STATUS_EVERY_SECONDS = 60

i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
chan = AnalogIn(ads, 0)

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUZZER_PIN, GPIO.OUT)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

occupied_start = None
last_status_time = 0
last_occupied = None
last_alarm = None
last_button = None

try:
    while True:
        now = time.time()

        volts = chan.voltage
        occupied = volts < LOW_THRESHOLD_VOLTS or volts > HIGH_THRESHOLD_VOLTS
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

        alarm = button_pressed or delayed_alarm

        if button_pressed:
            buzzer_on = True

        elif delayed_alarm:
            if occupied_time < 25:
                phase_time = occupied_time - DELAY_SECONDS
                interval = 1.50 - (phase_time / 15.0)
                if interval < 0.20:
                    interval = 0.20
                buzzer_on = (now % interval) < 0.08
            else:
                buzzer_on = True

        else:
            buzzer_on = False

        GPIO.output(BUZZER_PIN, 1 if buzzer_on else 0)

        state_changed = (
            occupied != last_occupied or
            alarm != last_alarm or
            button_pressed != last_button
        )

        status_due = (now - last_status_time) >= STATUS_EVERY_SECONDS

        if state_changed or status_due:
            print(
                f"volts={volts:.3f} "
                f"occupied={occupied} "
                f"occupied_time={occupied_time:.1f} "
                f"button={button_pressed} "
                f"alarm={alarm} "
                f"buzzer={buzzer_on}"
            )
            last_status_time = now
            last_occupied = occupied
            last_alarm = alarm
            last_button = button_pressed

        time.sleep(0.2)

except KeyboardInterrupt:
    GPIO.output(BUZZER_PIN, 0)
    GPIO.cleanup()
