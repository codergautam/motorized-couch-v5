import math
from typing import Tuple
import mathutils
import Gamepad.Controllers as Controllers

SLOW_SPEED = 1
MEDIUM_SPEED = 1
MAX_SPEED = 1

def curvture_drive_ik(speed: float, rotation: float) -> Tuple[float, float]:
    """Curvature drive inverse kinematics for a differential drive platform.

    Args:
      speed: The speed along the X axis [-1.0..1.0]. Forward is positive.
      rotation: The normalized curvature [-1.0..1.0]. Counterclockwise is positive.

    Returns:
      Wheel speeds [-1.0..1.0].
    """
    speed, rotation = mathutils.scale_and_deadzone_inputs(speed, rotation, square_rotation=False)
    left_speed = speed + abs(speed) * rotation
    right_speed = speed - abs(speed) * rotation
    return mathutils.desaturate_wheel_speeds(left_speed, right_speed)


def arcade_drive_ik(speed: float, rotation: float) -> Tuple[float, float]:
    """Arcade drive inverse kinematics for a differential drive platform.

    Args:
      speed: The speed along the X axis [-1.0..1.0]. Forward is positive.
      rotation: The normalized curvature [-1.0..1.0]. Counterclockwise is positive.

    Returns:
      Wheel speeds [-1.0..1.0].
    """
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
