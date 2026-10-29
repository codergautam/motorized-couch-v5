"""Which joystick axes and buttons drive the couch.

Set up for a Logitech F310 gamepad with the switch on its back set to X, driven
like a racing game. On D it shows up as a different device with its buttons in
a different order, so it's ignored rather than driving the couch with the
wrong buttons.

For a different controller, run `uv run joystick_probe.py` with it plugged in
to see the names it uses, then put them here.
"""
from typing import Dict, List, Optional

from joystick import AxisCalibration

# Part of the device name. None uses the first joystick or gamepad found.
JOYSTICK_NAME: Optional[str] = "F310"

GAS_AXIS = "ABS_RZ"  # right trigger
BRAKE_AXIS = "ABS_Z"  # left trigger
STEERING_AXIS = "ABS_RX"  # right stick

# Thumbsticks rarely rest exactly centered and the F310 barely reports a
# deadzone of its own. If the probe shows the stick off +0.00 when you let go,
# raise this, otherwise the couch creeps or never arms.
STICK_DEADZONE = 0.15
TRIGGER_DEADZONE = 0.05

# Everything but driving is on the d-pad, the face buttons do nothing. The F310
# reports its d-pad as two axes, -1 up / left and +1 down / right.
# Up picks drive and down picks reverse, only while the couch isn't moving.
GEAR_AXIS = "ABS_HAT0Y"
# Left and right step through park, neutral, chill, standard and sport, the
# same order as on the screen
SPEED_MODE_AXIS = "ABS_HAT0X"

AXIS_CALIBRATION: Dict[str, AxisCalibration] = {
    # Triggers rest at their minimum, so centering them there reads 0 released and 1 pulled
    GAS_AXIS: AxisCalibration(center=0, deadzone=TRIGGER_DEADZONE),
    BRAKE_AXIS: AxisCalibration(center=0, deadzone=TRIGGER_DEADZONE),
    STEERING_AXIS: AxisCalibration(deadzone=STICK_DEADZONE),
    # Inverted so up reads +1
    GEAR_AXIS: AxisCalibration(invert=True, deadzone=0.5),
    SPEED_MODE_AXIS: AxisCalibration(deadzone=0.5),
}

HORN_BUTTONS: List[str] = ["BTN_TL"]  # left bumper
