import tkinter as tk
from ScreenUI import ScreenUI  # Assuming tkinter_ui.py is the file with the ScreenUI class
import time
import threading
from typing import Tuple

import Gamepad.Gamepad as Gamepad
import Gamepad.Controllers as Controllers
from detect_motor_controllers import get_motor_controllers
import mathutils

from drive_modes import arcade_drive_ik, get_speed_multiplier
import pygame

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
voltage = 0
temperature = 0
couch_mode = 0 # 0 = park, 1 = neutral, 2 = chill, 3 = speed, 4 = ludicrous 

def update_ui_periodically(app):
    count = 70
    while True:
        app.update_ui(int(speed), odo, left_power, right_power, debugInfo, couch_mode)
        count += 1
        time.sleep(0.2)  # Update 5 times a second

def joystick_motor_control():
    global speed
    global odo
    global left_power
    global right_power
    global debugInfo
    global voltage
    global temperature
    global couch_mode
    # Waits for the joystick to be connected
    while not Gamepad.available():
        print("Please connect your gamepad")
        time.sleep(1)
    joystick = Controllers.Joystick()  # Initializes the joystick as a generic gamepad
    print("Gamepad connected")

    #pygame.mixer.init()

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

            rpm_to_mph = 8 * 3.14 * 60 / 5280 / 12

            speed = (((left_rpm + right_rpm) / 2) / 15) * rpm_to_mph #Convert ERPM to RPM

            if joystick.isPressed('T1'):
                couch_mode = 0
                left_motor.set_rpm(0)
                right_motor.set_rpm(0)
                print("Motors set to brake state (park)")
            elif joystick.isPressed('T2'):
                couch_mode = 1
                left_motor.set_current(0) 
                right_motor.set_current(0)
                print("Motors set to loose state (neutral)")
            elif joystick.isPressed('T3'):
                couch_mode = 2
                print("Motors set to brake state (chill)")
            elif joystick.isPressed('T5'):
                couch_mode = 3
                print("Motors set to brake state (speed)")
            elif joystick.isPressed('T7'):
                couch_mode = 4
                print("Motors set to brake state (ludicrous)")

            if joystick.isPressed('TRIGGER'):
                try:
                    pygame.mixer.music.load("horn2.wav")
                    pygame.mixer.music.play()
                    print("Playing sound")
                except Exception as e:
                    print(f"Failed to play sound: {e}")

            if couch_mode > 1:
                left_motor.set_rpm(ik_left)
                right_motor.set_rpm(ik_right)

            try:
                measurements_left = left_motor.get_measurements()
                measurements_right = right_motor.get_measurements()

                left_power = measurements_left.avg_motor_current * 10
                right_power = measurements_right.avg_motor_current * 10
                voltage = measurements_left.v_in
                temperature = measurements_left.temp_fet if measurements_left.temp_fet > measurements_right.temp_fet else measurements_right.motor_temp
            except:
                pass

    finally:
        del left_motor
        del right_motor
        joystick.disconnect()

if __name__ == "__main__":
    print("Starting main program")
    root = tk.Tk()
    app = ScreenUI(root)

    # Use a separate thread to update the UI periodically
    update_thread = threading.Thread(target=update_ui_periodically, args=(app,))
    update_thread.daemon = True  # This will allow the thread to exit when the main program exits
    update_thread.start()

    # Use a separate thread for joystick and motor control
    control_thread = threading.Thread(target=joystick_motor_control)
    control_thread.daemon = True  # This will allow the thread to exit when the main program exits
    control_thread.start()

    print("Starting UI")
    root.mainloop()
    print("UI exited")
