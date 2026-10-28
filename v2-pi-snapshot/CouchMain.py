import tkinter as tk
from ScreenUI import ScreenUI  # Assuming tkinter_ui.py is the file with the ScreenUI class
import time
import threading
from typing import Tuple

import Gamepad.Gamepad as Gamepad
import Gamepad.Controllers as Controllers
import time
from detect_motor_controllers import get_motor_controllers
import mathutils

from drive_modes import arcade_drive_ik, get_speed_multiplier
from playsound import playsound


SLOW_SPEED = 0.3
MEDIUM_SPEED = 0.5
MAX_SPEED = 1

VERTICAL_JOYSTICK_AXIS = 1
HORIZONTAL_JOYSTICK_AXIS = 0
POLL_INTERVAL = 0.1

speed = 0
odo = 0
left_power = 0
right_power = 0
debugInfo = ""
left_rpm = 0
right_rpm = 0

def update_ui_periodically(app):
    count = 70
    while True:
        app.update_ui(speed, odo, left_power, right_power, debugInfo)
        count += 1
        time.sleep(0.2)  # Update 5 times a second

if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenUI(root)

    # Use a separate thread to update the UI periodically
    update_thread = threading.Thread(target=update_ui_periodically, args=(app,))
    update_thread.daemon = True  # This will allow the thread to exit when the main program exits
    update_thread.start()

    root.mainloop()

    # Waits for the joystick to be connected
    while not Gamepad.available():
        print("Please connect your gamepad")
        time.sleep(1)
    joystick = Controllers.Joystick()  # Initializes the joystick as a generic gamepad
    print("Gamepad connected")

    joystick.startBackgroundUpdates()

    # Waits for the motor controllers to be connected
    left_motor, right_motor = get_motor_controllers()

    # Main loop
    try:
        while joystick.isConnected():
            joystick_vertical = -joystick.axis('Y')
            joystick_horizontal = joystick.axis('X')
            ik_left, ik_right = arcade_drive_ik(joystick_vertical, joystick_horizontal)
            ik_left *= get_speed_multiplier(joystick)
            ik_right *= get_speed_multiplier(joystick)

            try:
                left_rpm = left_motor.get_rpm()
                right_rpm = right_motor.get_rpm()
            except:
                left_rpm = 0
                right_rpm = 0

            print(f"Left: {ik_left}, Right: {ik_right}, Left RPM: {left_rpm}, Right RPM {right_rpm}")

            # if(joystick.isPressed('TRIGGER')):
            #     playsound(sound_file)

            left_motor.set_rpm(ik_left)
            right_motor.set_rpm(ik_right)

            measurements_left = left_motor.get_measurements()
            measurements_right = right_motor.get_measurements()

            print(f"Left: {measurements_left}, Right: {measurements_right}")

                
    finally:
        del left_motor
        del right_motor
        joystick.disconnect()