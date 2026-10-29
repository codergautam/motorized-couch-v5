import time
import threading

from detect_motor_controllers import get_motor_controllers
from joystick import JoystickAdapter, code
from joystick_config import (
    JOYSTICK_NAME, GAS_AXIS, BRAKE_AXIS, STEERING_AXIS, AXIS_CALIBRATION, GEAR_BUTTONS, SPEED_MODE_BUTTONS, HORN_BUTTONS
)

from battery import voltage_to_percentage
from drive_modes import Gear, RacingThrottle, SpeedMode, arcade_drive_ik, get_speed_multiplier
from mathutils import InputSmoother

from screen_ui import ScreenUI, ScreenUIUpdate

POLL_INTERVAL = 0.05  # 20Hz polling for more responsive input reading

# Fraction of full speed lost per second after letting go of the gas (about 2 s
# from full speed to stopped), and with the brake pulled all the way
COAST_RATE = 0.5
BRAKE_RATE = 3.0
REVERSE_SPEED_MODE: SpeedMode = "chill"  # reverse is never faster than this

IPM_IN_MPH = 1056
POLE_PAIRS = 6
MOTOR_PULLEY = 16
WHEEL_PULLEY = 72

class Couch:
    def __init__(self, ui_manager: "ScreenUI | None" = None):
        self.ui_manager = ui_manager
        self.speed = 0
        self.left_power = 0
        self.right_power = 0
        self.left_rpm = 0
        self.right_rpm = 0
        self.voltage = 0
        self.temperature = 0
        self.speed_mode: SpeedMode = "park"
        
        # Input smoothing to prevent oscillation from physical feedback
        # Lower smoothing_factor = more responsive (0.3 is a good balance)
        # Lower max_accel_per_sec = smoother acceleration changes
        self.input_smoother = InputSmoother(
            smoothing_factor=0.3,  # Light smoothing to maintain responsiveness
            max_accel_per_sec=4.0   # Allow reasonably quick acceleration changes
        )
        
        # Rotation sensitivity - makes turning less aggressive than forward/backward
        self.rotation_sensitivity = 0.3  # 70% less sensitive turning

        # Config names are resolved up front so a typo fails at startup, not mid-drive
        self.joystick = JoystickAdapter(JOYSTICK_NAME, AXIS_CALIBRATION)
        self.gas_axis = code(GAS_AXIS)
        self.brake_axis = code(BRAKE_AXIS)
        self.steering_axis = code(STEERING_AXIS)
        self.gear_buttons = [code(button) for button in GEAR_BUTTONS]
        self.speed_mode_buttons = [
            (mode, [code(button) for button in buttons]) for mode, buttons in SPEED_MODE_BUTTONS.items()
        ]
        self.horn_buttons = [code(button) for button in HORN_BUTTONS]

        self.throttle = RacingThrottle(COAST_RATE, BRAKE_RATE)
        self.gear: Gear = "drive"
        self.gear_was_pressed = False
        # The couch won't drive until the gas is released and the stick centered
        # in a drive mode, so leaving park or reconnecting with either held doesn't lurch
        self.armed = False

    def start(self):
        print("Starting couch")
        self.stop_event = threading.Event()
        self.joystick.start()

        # Use a separate thread for joystick and motor control
        self.control_thread = threading.Thread(target=self.joystick_motor_control, daemon=True)
        self.ui_thread = threading.Thread(target=self.update_ui_periodically, daemon=True)
        self.control_thread.start()
        self.ui_thread.start()
        print("Started couch")

    def stop(self):
        print("Stopping couch")
        self.stop_event.set()
        self.control_thread.join()
        print("Stopped control thread")
        self.joystick.stop()
        print("Stopped joystick")
        self.ui_thread.join()
        print("Stopped UI thread")
        print("Stopped couch")

    def update_ui_periodically(self):
        stop_event = self.stop_event
        while not stop_event.is_set():
            battery_percentage = voltage_to_percentage(self.voltage)
            wattage = self.left_power + self.right_power
            try:
                if self.ui_manager:
                    self.ui_manager.update(ScreenUIUpdate(
                        speed_mph=self.speed,
                        power_watts=wattage,
                        battery_pct=battery_percentage,
                        speed_mode=self.speed_mode,
                        gear=self.gear,
                    ))
            except Exception as e:
                print(f"Error sending data to UI: {e}")
            time.sleep(0.2)

    def joystick_motor_control(self):
        stop_event = self.stop_event

        #pygame.mixer.init()

        # Waits for the motor controllers to be connected
        left_motor, right_motor = get_motor_controllers()

        # Main loop
        try:
            while not stop_event.is_set():
                joystick = self.joystick.state()

                if not joystick.connected:
                    # Lost the joystick, so brake, go back to drive and make the driver pick a mode again
                    self.speed_mode = "park"
                    self.gear = "drive"
                else:
                    for mode, buttons in self.speed_mode_buttons:
                        if joystick.any_pressed(buttons):
                            self.speed_mode = mode
                            break

                # Normalized and calibrated by the adapter: triggers [0..1], steering right is positive
                gas = joystick.axis(self.gas_axis)
                brake = joystick.axis(self.brake_axis)
                steering = joystick.axis(self.steering_axis)

                if self.speed_mode in ("park", "neutral"):
                    self.armed = False
                elif gas == 0 and steering == 0:
                    self.armed = True
                if not self.armed:
                    gas = steering = 0
                    self.throttle.reset()

                speed = self.throttle.update(gas, brake)

                # Shift once per press, and only while the couch isn't being driven
                gear_pressed = joystick.any_pressed(self.gear_buttons)
                if gear_pressed and not self.gear_was_pressed:
                    if speed == 0 and steering == 0:
                        self.gear = "reverse" if self.gear == "drive" else "drive"
                    else:
                        print("Stop before shifting gear")
                self.gear_was_pressed = gear_pressed

                # Apply input smoothing to prevent oscillation from physical feedback
                #smooth_speed, smooth_steering = self.input_smoother.smooth_inputs(speed, steering)

                # Steering flips in reverse, like backing up a car
                direction = -1 if self.gear == "reverse" else 1
                ik_left, ik_right = arcade_drive_ik(direction * speed, direction * steering, self.rotation_sensitivity)

                speed_multiplier = get_speed_multiplier(self.speed_mode)
                if self.gear == "reverse":
                    speed_multiplier = min(speed_multiplier, get_speed_multiplier(REVERSE_SPEED_MODE))
                ik_left *= speed_multiplier
                ik_right *= speed_multiplier

                try:
                    measurements_left = left_motor.get_measurements()
                    measurements_right = right_motor.get_measurements()

                    if measurements_left and measurements_right:
                        self.left_rpm = measurements_left.rpm
                        self.right_rpm = measurements_right.rpm
                        self.left_power = measurements_left.avg_motor_current * 10
                        self.right_power = measurements_right.avg_motor_current * 10
                        self.voltage = measurements_left.v_in
                        self.temperature = measurements_left.temp_fet if measurements_left.temp_fet > measurements_right.temp_fet else measurements_right.temp_fet
                    else:
                        self.left_rpm = 0
                        self.right_rpm = 0
                except Exception as e:
                    print(f"Error getting motor measurements: {e}")
                    self.left_rpm = 0
                    self.right_rpm = 0

                avg_erpm = (self.left_rpm + self.right_rpm) / 2
                motor_rpm = avg_erpm / POLE_PAIRS
                wheel_rpm = motor_rpm * (MOTOR_PULLEY / WHEEL_PULLEY)
                wheel_mph = wheel_rpm * 8 * 3.14 / IPM_IN_MPH

                self.speed = wheel_mph

                if self.speed_mode == "neutral":
                    left_motor.set_current(0)
                    right_motor.set_current(0)
                else:
                    left_motor.set_rpm(ik_left)
                    right_motor.set_rpm(ik_right)

                if joystick.any_pressed(self.horn_buttons):
                    # TODO: Horn
                    pass

                # Control loop timing
                time.sleep(POLL_INTERVAL)

        finally:
            del left_motor
            del right_motor


if __name__ == "__main__":
    main = Couch()
    main.start()
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        main.stop()
    
