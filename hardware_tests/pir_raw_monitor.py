from gpiozero import DigitalInputDevice
from datetime import datetime
import time

pir = DigitalInputDevice(17, pull_up=False)

last_state = None
started = time.time()

print("Raw PIR monitor on GPIO17")
print("CTRL+C to stop")

while True:
    state = pir.value
    if state != last_state:
        now = time.time()
        print(datetime.now().strftime("%H:%M:%S"), "GPIO17 =", int(state), "previous lasted", round(now - started, 2), "s")
        last_state = state
        started = now
    time.sleep(0.2)
