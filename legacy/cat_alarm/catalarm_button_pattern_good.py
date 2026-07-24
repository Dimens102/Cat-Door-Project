import time
import RPi.GPIO as GPIO

BUZZER_PIN = 18
BUTTON_PIN = 17

BEEP_LENGTH = 0.07
COUNTDOWN_SECONDS = 45.0
START_INTERVAL = 5.00
END_INTERVAL = 0.08

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUZZER_PIN, GPIO.OUT)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

button_start = None
last_beep_time = 0

try:
    while True:
        now = time.time()
        button_pressed = GPIO.input(BUTTON_PIN) == 0

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

        print(f"button={button_pressed} buzzer={buzzer_on}")
        time.sleep(0.02)

except KeyboardInterrupt:
    GPIO.output(BUZZER_PIN, 0)
    GPIO.cleanup()
