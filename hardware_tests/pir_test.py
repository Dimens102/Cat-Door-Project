from gpiozero import MotionSensor
from signal import pause

pir = MotionSensor(17)

print("PIR test running...")
pir.when_motion = lambda: print("MOTION DETECTED")
pir.when_no_motion = lambda: print("Motion ended")

pause()
