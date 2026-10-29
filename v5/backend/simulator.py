"""Drive a simulated couch with the real controls, no motors involved.

    uv run simulator.py

Runs the real couch control loop and dashboard, but with simulated motor
controllers. A second window shows the couch from above along with exactly
what would be sent to each motor. On Linux the joystick is read exactly the way
the couch reads it. On Windows it's read through XInput, so the F310 needs its
switch on X.
"""
import ctypes
import math
import sys
import time
import tkinter as tk
import types
from ctypes import wintypes

if sys.platform == "win32":
    # joystick.py needs evdev, which only exists on Linux, and the couch only
    # uses it for event codes. These are the gamepad ones from linux/input-event-codes.h.
    GAMEPAD_CODES = {
        "ABS_X": 0x00, "ABS_Y": 0x01, "ABS_Z": 0x02, "ABS_RX": 0x03, "ABS_RY": 0x04, "ABS_RZ": 0x05,
        "ABS_HAT0X": 0x10, "ABS_HAT0Y": 0x11,
        "BTN_A": 0x130, "BTN_SOUTH": 0x130, "BTN_B": 0x131, "BTN_EAST": 0x131,
        "BTN_X": 0x133, "BTN_NORTH": 0x133, "BTN_Y": 0x134, "BTN_WEST": 0x134,
        "BTN_TL": 0x136, "BTN_TR": 0x137, "BTN_SELECT": 0x13a, "BTN_START": 0x13b,
        "BTN_MODE": 0x13c, "BTN_THUMBL": 0x13d, "BTN_THUMBR": 0x13e,
    }
    fake_evdev = types.ModuleType("evdev")
    fake_evdev.ecodes = types.SimpleNamespace(ecodes=GAMEPAD_CODES)  # pyright: ignore[reportAttributeAccessIssue]
    sys.modules["evdev"] = fake_evdev

import couch  # noqa: E402
from couch import Couch, POLE_PAIRS, MOTOR_PULLEY, WHEEL_PULLEY  # noqa: E402
from joystick import AxisCalibration, JoystickState, code, normalize  # noqa: E402
from joystick_config import AXIS_CALIBRATION  # noqa: E402
from motor_controller import MotorController  # noqa: E402
from screen_ui import ScreenUI  # noqa: E402

WHEEL_DIAMETER = 8 * 0.0254  # m, the 8" wheels couch.py's speed calculation uses
ERPM_TO_MPS = (1 / POLE_PAIRS) * (MOTOR_PULLEY / WHEEL_PULLEY) * math.pi * WHEEL_DIAMETER / 60
TRACK_WIDTH = 1.6  # m between the wheels, a guess
COUCH_WIDTH = 2.0  # m
COUCH_DEPTH = 0.9  # m
MOTOR_ACCEL = 15000  # erpm per second the simulated motors can speed up or slow down, a guess
ROLL_DECEL = 2000  # erpm per second lost rolling freely in neutral, a guess
PIXELS_PER_METER = 30
VIEW_WIDTH, VIEW_HEIGHT = 800, 600


class SimMotor(MotorController):
    """Stands in for a VESC: chases the commanded RPM as fast as MOTOR_ACCEL
    allows, or rolls freely when given zero current (neutral)."""

    def __init__(self):
        self.erpm = 0.0
        self.target_erpm = 0
        self.free = False
        self.command = 0.0  # the last speed [-1..1] the couch asked for

    def set_rpm(self, speed: float):
        self.command = speed
        self.target_erpm = self.speed_to_rpm(speed)
        self.free = False

    def set_current(self, speed: float):
        self.command = 0.0
        self.free = True

    def get_measurements(self):
        return types.SimpleNamespace(rpm=self.erpm, avg_motor_current=abs(self.erpm) / 2000, v_in=50.4, temp_fet=35.0)

    def step(self, dt: float):
        target, rate = (0.0, ROLL_DECEL) if self.free else (self.target_erpm, MOTOR_ACCEL)
        self.erpm += max(-rate * dt, min(rate * dt, target - self.erpm))


class _XInputGamepad(ctypes.Structure):
    _fields_ = [("wButtons", wintypes.WORD), ("bLeftTrigger", ctypes.c_ubyte), ("bRightTrigger", ctypes.c_ubyte),
                ("sThumbLX", ctypes.c_short), ("sThumbLY", ctypes.c_short),
                ("sThumbRX", ctypes.c_short), ("sThumbRY", ctypes.c_short)]


class _XInputState(ctypes.Structure):
    _fields_ = [("dwPacketNumber", wintypes.DWORD), ("Gamepad", _XInputGamepad)]


class XInputJoystick:
    """Reads an Xbox-style controller through Windows XInput and reports it the
    same way JoystickAdapter does for that controller on Linux, where the xpad
    driver flips Y and reports sticks as -32768..32767 and triggers as 0..255."""

    STICK = types.SimpleNamespace(min=-32768, max=32767, flat=128)
    TRIGGER = types.SimpleNamespace(min=0, max=255, flat=0)
    HAT = types.SimpleNamespace(min=-1, max=1, flat=0)
    BUTTONS = {
        0x1000: "BTN_A", 0x2000: "BTN_B", 0x4000: "BTN_X", 0x8000: "BTN_Y", 0x0100: "BTN_TL", 0x0200: "BTN_TR",
        0x0010: "BTN_START", 0x0020: "BTN_SELECT", 0x0040: "BTN_THUMBL", 0x0080: "BTN_THUMBR",
    }

    def __init__(self):
        self.xinput = ctypes.windll.xinput1_4  # pyright: ignore[reportAttributeAccessIssue]
        self.calibration = {code(name): calibration for name, calibration in AXIS_CALIBRATION.items()}
        self.buttons = {bit: code(name) for bit, name in self.BUTTONS.items()}
        self.index = None
        self.last_scan = 0.0

    def start(self):
        pass

    def stop(self):
        pass

    def state(self) -> JoystickState:
        pad = self._read()
        if pad is None:
            return JoystickState()
        raw = {
            code("ABS_X"): pad.sThumbLX, code("ABS_Y"): ~pad.sThumbLY,
            code("ABS_RX"): pad.sThumbRX, code("ABS_RY"): ~pad.sThumbRY,
            code("ABS_Z"): pad.bLeftTrigger, code("ABS_RZ"): pad.bRightTrigger,
            # The d-pad is buttons in XInput but an axis on Linux, -1 left/up and +1 right/down
            code("ABS_HAT0X"): bool(pad.wButtons & 0x0008) - bool(pad.wButtons & 0x0004),
            code("ABS_HAT0Y"): bool(pad.wButtons & 0x0002) - bool(pad.wButtons & 0x0001),
        }
        triggers = (code("ABS_Z"), code("ABS_RZ"))
        hats = (code("ABS_HAT0X"), code("ABS_HAT0Y"))

        def info(axis: int):
            return self.TRIGGER if axis in triggers else self.HAT if axis in hats else self.STICK

        axes = {
            axis: normalize(value, info(axis), self.calibration.get(axis, AxisCalibration()))
            for axis, value in raw.items()
        }
        pressed = frozenset(button for bit, button in self.buttons.items() if pad.wButtons & bit)
        return JoystickState(connected=True, name="XInput controller", axes=axes, raw_axes=raw, pressed=pressed)

    def _read(self):
        state = _XInputState()
        if self.index is not None and self.xinput.XInputGetState(self.index, ctypes.byref(state)) == 0:
            return state.Gamepad
        self.index = None
        # Polling empty slots is slow, so only look for a controller once a second
        if time.monotonic() - self.last_scan < 1:
            return None
        self.last_scan = time.monotonic()
        for index in range(4):
            if self.xinput.XInputGetState(index, ctypes.byref(state)) == 0:
                self.index = index
                return state.Gamepad
        return None


class TopDownView:
    """Moves the couch around a floor using the simulated wheel speeds, seen from
    above with the camera following it, plus what the controls and motors are doing."""

    def __init__(self, window: tk.Misc, sim_couch: Couch, left: SimMotor, right: SimMotor):
        self.couch = sim_couch
        self.left = left
        self.right = right
        self.canvas = tk.Canvas(window, width=VIEW_WIDTH, height=VIEW_HEIGHT, bg="#f3f4f6", highlightthickness=0)
        self.canvas.pack()
        self.x = 0.0
        self.y = 0.0
        self.heading = math.pi / 2  # facing up the screen
        self.speed = 0.0
        self.trail = [(0.0, 0.0)]
        self.last_time = time.monotonic()
        self.tick()

    def tick(self):
        now = time.monotonic()
        dt = now - self.last_time
        self.last_time = now

        self.left.step(dt)
        self.right.step(dt)
        left_speed = self.left.erpm * ERPM_TO_MPS
        right_speed = self.right.erpm * ERPM_TO_MPS
        self.speed = (left_speed + right_speed) / 2
        self.heading += (right_speed - left_speed) / TRACK_WIDTH * dt
        self.x += self.speed * math.cos(self.heading) * dt
        self.y += self.speed * math.sin(self.heading) * dt
        last_x, last_y = self.trail[-1]
        if math.hypot(self.x - last_x, self.y - last_y) > 0.1:
            self.trail = self.trail[-600:] + [(self.x, self.y)]

        self.draw()
        self.canvas.after(20, self.tick)

    def to_screen(self, x: float, y: float):
        return (VIEW_WIDTH / 2 + (x - self.x) * PIXELS_PER_METER,
                VIEW_HEIGHT / 2 - (y - self.y) * PIXELS_PER_METER)

    def draw(self):
        canvas = self.canvas
        canvas.delete("all")

        # 1 m floor grid, darker every 5 m
        half_w = VIEW_WIDTH / 2 / PIXELS_PER_METER
        half_h = VIEW_HEIGHT / 2 / PIXELS_PER_METER
        for gx in range(math.floor(self.x - half_w), math.ceil(self.x + half_w) + 1):
            sx, _ = self.to_screen(gx, 0)
            canvas.create_line(sx, 0, sx, VIEW_HEIGHT, fill="#9ca3af" if gx % 5 == 0 else "#e5e7eb")
        for gy in range(math.floor(self.y - half_h), math.ceil(self.y + half_h) + 1):
            _, sy = self.to_screen(0, gy)
            canvas.create_line(0, sy, VIEW_WIDTH, sy, fill="#9ca3af" if gy % 5 == 0 else "#e5e7eb")

        if len(self.trail) > 1:
            canvas.create_line(*[p for point in self.trail + [(self.x, self.y)] for p in self.to_screen(*point)],
                               fill="#0079FF", width=2)

        # The couch: forward is the way it's facing, its wheels are on its left and right ends
        fx, fy = math.cos(self.heading), math.sin(self.heading)
        rx, ry = fy, -fx

        def at(forward: float, rightward: float):
            return self.to_screen(self.x + forward * fx + rightward * rx, self.y + forward * fy + rightward * ry)

        d, w = COUCH_DEPTH / 2, COUCH_WIDTH / 2
        canvas.create_polygon(*at(d, -w), *at(d, w), *at(-d, w), *at(-d, -w), fill="#d6c4a8", outline="#111827", width=2)
        canvas.create_line(*at(-d + 0.1, -w + 0.1), *at(-d + 0.1, w - 0.1), fill="#7c5c3b", width=8)  # backrest
        canvas.create_polygon(*at(d + 0.35, 0), *at(d + 0.05, -0.2), *at(d + 0.05, 0.2), fill="#111827")  # front
        for motor, side in ((self.left, -w), (self.right, w)):
            color = "#00DFA2" if motor.erpm > 1 else "#FF0060" if motor.erpm < -1 else "#111827"
            canvas.create_line(*at(0.25, side), *at(-0.25, side), fill=color, width=10)

        canvas.create_text(12, 10, anchor="nw", font="TkFixedFont", text="\n".join(self.hud_lines()), fill="#111827")

    def hud_lines(self):
        joystick = self.couch.joystick.state()
        if not joystick.connected:
            return ["CONTROLLER NOT FOUND", "Plug in the F310 with the switch on the back on X", "", "Couch is parked"]

        def bar(value: float, signed: bool = False):
            cells = 20
            if signed:
                filled = round(abs(value) * cells / 2)
                left = "#" * filled if value < 0 else ""
                right = "#" * filled if value > 0 else ""
                return f"[{left:>10}|{right:<10}] {value:+.2f}"
            return f"[{'#' * round(value * cells):<{cells}}] {value:.2f}"

        mode = self.couch.speed_mode
        lines = [f"{mode.upper()}   {self.couch.gear.upper()}"]
        if self.couch.parking:
            lines.append("Braking to a stop, then parking")
        elif mode in ("park", "neutral"):
            lines.append("Press right on the d-pad to pick a drive mode")
        elif not self.couch.armed:
            lines.append("Let go of the gas and center the stick to drive")
        else:
            lines.append("Ready")
        lines += [
            "",
            f"gas    {bar(joystick.axis(self.couch.gas_axis))}",
            f"brake  {bar(joystick.axis(self.couch.brake_axis))}",
            f"steer  {bar(joystick.axis(self.couch.steering_axis), signed=True)}",
            "",
            "sent to motors:",
        ]
        for name, motor in (("left ", self.left), ("right", self.right)):
            command = "free spin (neutral)" if motor.free else f"set_rpm {motor.target_erpm:+6d} erpm  ({motor.command:+.2f})"
            lines.append(f"  {name} {command}")
        lines += ["", f"speed  {abs(self.speed) * 2.23694:4.1f} mph"]
        return lines


def main():
    root = tk.Tk()
    ui = ScreenUI(root)
    # ScreenUI fills the Pi's screen, which is the same size as the dashboard,
    # so it stays fullscreen there. Anywhere else it's just a window.
    if sys.platform != "linux":
        root.attributes("-fullscreen", False)
        root.geometry("800x480+20+20")
    root.title("Couch dashboard (simulated motors)")

    left, right = SimMotor(), SimMotor()
    couch.get_motor_controllers = lambda: (left, right)
    sim_couch = Couch(ui)
    if sys.platform == "win32":
        sim_couch.joystick = XInputJoystick()  # pyright: ignore[reportAttributeAccessIssue]

    window = tk.Toplevel(root)
    window.title("Couch simulator")
    window.geometry(f"{VIEW_WIDTH}x{VIEW_HEIGHT}+840+20")
    TopDownView(window, sim_couch, left, right)

    root.protocol("WM_DELETE_WINDOW", root.quit)
    window.protocol("WM_DELETE_WINDOW", root.quit)
    sim_couch.start()
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    # Stopped outside the main loop, like main.py, so the UI thread can't deadlock on Tk
    sim_couch.stop()
    root.destroy()


if __name__ == "__main__":
    main()
