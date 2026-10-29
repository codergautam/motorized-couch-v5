"""Shows exactly what the couch reads from the joystick.

    uv run joystick_probe.py

Lists the input devices, then prints the axes (normalized with the calibration
from joystick_config.py, raw value in brackets) and pressed buttons every time
something changes. Use the names it prints in joystick_config.py.
"""
import time

import evdev  # pyright: ignore[reportMissingImports]
from evdev import ecodes  # pyright: ignore[reportMissingImports]

from joystick import JoystickAdapter, code_name, is_joystick
from joystick_config import JOYSTICK_NAME, AXIS_CALIBRATION


def main():
    print("Input devices:")
    for path in sorted(evdev.list_devices()):
        device = evdev.InputDevice(path)
        kind = "joystick" if is_joystick(device) else ""
        print(f"  {path:<20} {device.info.vendor:04x}:{device.info.product:04x}  {device.name:<40} {kind}")
        device.close()
    print()

    print("Move the stick and press buttons, Ctrl+C to quit")
    joystick = JoystickAdapter(JOYSTICK_NAME, AXIS_CALIBRATION)
    joystick.start()
    last_line = None
    try:
        while True:
            state = joystick.state()
            if not state.connected:
                last_line = None  # the adapter prints connects and disconnects itself
            else:
                axes = "  ".join(
                    f"{code_name(ecodes.EV_ABS, axis)} {value:+.2f} [{state.raw_axes[axis]}]"
                    for axis, value in sorted(state.axes.items())
                )
                pressed = " ".join(code_name(ecodes.EV_KEY, button) for button in sorted(state.pressed))
                line = f"{axes}  pressed: {pressed or '-'}"
                if line != last_line:
                    print(line)
                    last_line = line
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        joystick.stop()


if __name__ == "__main__":
    main()
