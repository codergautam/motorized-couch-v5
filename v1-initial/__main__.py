import tkinter as tk
from tkinter import ttk
from typing import Tuple

import Gamepad.Gamepad as Gamepad
import Gamepad.Controllers as Controllers
import time
from detect_motor_controllers import get_motor_controllers
import mathutils
import os
os.environ['DISPLAY'] = ':0'


SLOW_SPEED = 0.3
MEDIUM_SPEED = 0.5
MAX_SPEED = 1

trigger = False

def curvture_drive_ik(speed: float, rotation: float) -> Tuple[float, float]:
    """Curvature drive inverse kinematics for a differential drive platform."""
    speed, rotation = mathutils.scale_and_deadzone_inputs(speed, rotation, square_rotation=False)
    left_speed = speed + abs(speed) * rotation
    right_speed = speed - abs(speed) * rotation
    return mathutils.desaturate_wheel_speeds(left_speed, right_speed)

def arcade_drive_ik(speed: float, rotation: float) -> Tuple[float, float]:
    """Arcade drive inverse kinematics for a differential drive platform."""
    speed, rotation = mathutils.scale_and_deadzone_inputs(speed, rotation)
    left_speed = speed + rotation
    right_speed = speed - rotation
    return mathutils.desaturate_wheel_speeds(left_speed, right_speed)

def get_speed_multiplier(stick: Controllers.Joystick) -> float:
    if stick.isPressed('MODEA'):
        return MEDIUM_SPEED
    elif stick.isPressed('MODEB'):
        return MAX_SPEED
    else:
        return SLOW_SPEED

def get_motor_current(motor_controller, can_id=None):
    try:
        if can_id is not None:
            motor_current = motor_controller.get_measurements(can_id=can_id).avg_motor_current
        else:
            motor_current = motor_controller.motor.get_measurements().avg_motor_current
        return motor_current
    except:
        return None
  

class MyApp:
    left_motor_current = 0
    right_motor_current = 0

    def __init__(self, root):
        self.root = root
        self.root.title("Full Screen Text Display")
        self.root.attributes('-fullscreen', True)  # Make the window full screen

        # Create a large text box to display text
        self.text_box = tk.Text(root, wrap=tk.WORD, font=('Helvetica', 16))
        self.text_box.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)

        # Insert some example text
        self.text_box.insert(tk.END, "This is a full-screen Tkinter window displaying text.\n")
        self.text_box.insert(tk.END, "You can add more information here as needed.\n")
        self.text_box.insert(tk.END, "Press 'Escape' to exit full screen.")

        # Bind the Escape key to exit full screen
        self.root.bind('<Escape>', self.exit_full_screen)

        self.poll_interval = 100  # Polling interval in milliseconds

        self.init_gamepad()

    def exit_full_screen(self, event):
        self.root.attributes('-fullscreen', False)  # Exit full screen

    def init_gamepad(self):
        self.joystick = None
        self.left_motor = None
        self.right_motor = None

        # Wait for the joystick to be connected
        self.check_gamepad()

    def check_gamepad(self):
        if not Gamepad.available():
            self.text_box.delete(1.0, tk.END)
            self.text_box.insert(tk.END, "Please connect your gamepad\n")
            self.root.after(1000, self.check_gamepad)
        else:
            self.joystick = Controllers.Joystick()
            self.joystick.startBackgroundUpdates()
            self.text_box.delete(1.0, tk.END)
            self.text_box.insert(tk.END, "Gamepad connected\n")
            self.left_motor, self.right_motor = get_motor_controllers()
            self.update_gamepad()


    def update_gamepad(self):
        if self.joystick.isConnected():
            # Retrieve joystick axis values
            axes = {name: self.joystick.axis(index) for index, name in self.joystick.axisNames.items()}
            
            # Retrieve joystick button values
            buttons = {name: self.joystick.isPressed(name) for index, name in self.joystick.buttonNames.items()}

            ik_left, ik_right = arcade_drive_ik(axes['Y'], axes['X'])
            ik_left *= get_speed_multiplier(self.joystick)
            ik_right *= get_speed_multiplier(self.joystick)

            left_motor_current = get_motor_current(self.left_motor)
            right_motor_current = get_motor_current(self.right_motor)            

            try:
                left_rpm = self.left_motor.get_rpm()
                right_rpm = self.right_motor.get_rpm()

            except:
                left_rpm = 0
                right_rpm = 0

            # Format the joystick values into a string
            joystick_values = (
                f"Axes: {axes}\n"
                f"Buttons: {buttons}\n"
                f"Left: {ik_left}, Right: {ik_right}\n"
                f"Left RPM: {left_rpm}, Right RPM: {right_rpm}\n"
                f"Left Motor Current: {left_motor_current}, Right Motor Current: {right_motor_current}"
            )

            # Update the text box with the new data
            self.text_box.delete(1.0, tk.END)
            self.text_box.insert(tk.END, joystick_values)

            if self.joystick.isPressed('TRIGGER'):
                self.left_motor.set_current(ik_left)
                self.right_motor.set_current(ik_right)
            else:
                self.left_motor.set_rpm(ik_left)
                self.right_motor.set_rpm(ik_right)

            self.root.after(self.poll_interval, self.update_gamepad)
        else:
            self.text_box.delete(1.0, tk.END)
            self.text_box.insert(tk.END, "Gamepad disconnected\n")
            self.joystick.disconnect()

if __name__ == '__main__':
    root = tk.Tk()
    app = MyApp(root)
    root.mainloop()
