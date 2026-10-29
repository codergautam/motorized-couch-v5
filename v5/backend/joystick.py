"""USB joystick / gamepad input through the Linux evdev interface.

Replaces the old /dev/input/js0 Gamepad library. Reading evdev directly means:
- axes are normalized using the range the device itself reports, instead of
  assuming every device is +-32767
- the real stick position is known as soon as the device is opened, instead of
  after the first event
- all values that changed together are applied together (one frame at a time)
- dropped events are recovered by re-reading the device, and unplugging and
  replugging the joystick reconnects automatically

Run joystick_probe.py to see what a device reports.
"""
import glob
import math
import select
import threading
import traceback
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Mapping, Optional

import evdev  # pyright: ignore[reportMissingImports]
from evdev import ecodes  # pyright: ignore[reportMissingImports]

RECONNECT_INTERVAL = 1.0  # seconds between looking for an unplugged joystick
READ_TIMEOUT = 0.25  # how often the reader thread checks whether it should stop


@dataclass(frozen=True)
class AxisCalibration:
    invert: bool = False
    # Raw value the axis rests at. None uses the middle of the device's range.
    center: Optional[int] = None
    # Fraction of travel [0..1) around center that reads as 0. None uses the
    # device's own "flat" value, which is what the old js0 driver applied, so
    # the stick feels the same as it did in V4.
    deadzone: Optional[float] = None


@dataclass(frozen=True)
class JoystickState:
    """One frame of joystick input. While disconnected every axis reads 0."""
    connected: bool = False
    name: str = ""
    axes: Mapping[int, float] = field(default_factory=dict)  # normalized [-1.0..1.0]
    raw_axes: Mapping[int, int] = field(default_factory=dict)
    pressed: FrozenSet[int] = frozenset()

    def axis(self, axis_code: int) -> float:
        return self.axes.get(axis_code, 0.0)

    def is_pressed(self, button_code: int) -> bool:
        return button_code in self.pressed

    def any_pressed(self, button_codes: Iterable[int]) -> bool:
        return any(button_code in self.pressed for button_code in button_codes)


def code(name: str) -> int:
    """Looks up an event code by name, e.g. "ABS_X" or "BTN_TRIGGER".
    Buttons without a name can be given as a number, e.g. "0x12c"."""
    if name in ecodes.ecodes:
        return ecodes.ecodes[name]
    try:
        return int(name, 0)
    except ValueError:
        raise ValueError(f"Unknown joystick code {name!r}, run joystick_probe.py to see valid names") from None


def code_name(event_type: int, event_code: int) -> str:
    """Name of an event code, e.g. "BTN_TRIGGER". Codes with several names
    (BTN_A is also BTN_SOUTH) come back as "BTN_A/BTN_GAMEPAD/BTN_SOUTH"."""
    name = ecodes.bytype[event_type].get(event_code)
    if name is None:
        return hex(event_code)
    if isinstance(name, str):
        return name
    return "/".join(name)


def normalize(raw: int, info, calibration: AxisCalibration) -> float:
    """Maps a raw axis value to [-1.0..1.0] using the device's reported range."""
    if info.max <= info.min:
        return 0.0
    center = calibration.center if calibration.center is not None else (info.min + info.max) / 2
    # Scale each side of center separately so full deflection always reaches
    # +-1, even when the stick doesn't rest in the exact middle of its range.
    span = info.max - center if raw >= center else center - info.min
    position = (raw - center) / span if span > 0 else 0.0
    position = max(-1.0, min(1.0, position))

    deadzone = calibration.deadzone
    if deadzone is None:
        deadzone = info.flat / ((info.max - info.min) / 2)
    deadzone = max(0.0, min(deadzone, 0.95))
    if abs(position) <= deadzone:
        return 0.0
    # Ramp up from 0 at the edge of the deadzone instead of jumping
    position = math.copysign((abs(position) - deadzone) / (1 - deadzone), position)
    return -position if calibration.invert else position


def is_joystick(device) -> bool:
    """True for joysticks and gamepads. Has to rule out the touchscreen, which
    also has X/Y axes but no joystick or gamepad buttons."""
    capabilities = device.capabilities(absinfo=False)
    axes = capabilities.get(ecodes.EV_ABS, [])
    buttons = capabilities.get(ecodes.EV_KEY, [])
    has_stick = ecodes.ABS_X in axes and ecodes.ABS_Y in axes
    # BTN_JOYSTICK (0x120) up to BTN_DIGI (0x140) covers BTN_TRIGGER... and BTN_SOUTH...
    has_joystick_buttons = any(ecodes.BTN_JOYSTICK <= button < ecodes.BTN_DIGI for button in buttons)
    return has_stick and has_joystick_buttons


def _open_all():
    devices = []
    for path in sorted(evdev.list_devices()):
        try:
            devices.append(evdev.InputDevice(path))
        except OSError:
            pass  # unplugged while scanning
    return devices


def joystick_names() -> List[str]:
    """Names of every plugged in joystick and gamepad."""
    devices = _open_all()
    names = [device.name for device in devices if is_joystick(device)]
    for device in devices:
        device.close()
    return names


def find_joystick(name: Optional[str] = None):
    """Opens the first plugged in joystick, or returns None if there isn't one.
    If name is given, only devices whose name contains it are considered."""
    devices = _open_all()
    matches = [device for device in devices if name is None or name.lower() in device.name.lower()]
    joysticks = [device for device in matches if is_joystick(device)]
    # A device picked by name is trusted even if it doesn't look like a
    # joystick, but one that does is preferred (a PS4 controller also shows up
    # as a touchpad and a motion sensor with the same name)
    candidates = joysticks or (matches if name is not None else [])
    chosen = candidates[0] if candidates else None
    for device in devices:
        if device is not chosen:
            device.close()
    return chosen


class JoystickAdapter:
    """Reads a joystick on a background thread. Call state() for the latest frame.

    Unplugging is handled here: state() reports connected=False with every axis
    at 0 and nothing pressed, and the joystick is reopened once it's back.
    """

    def __init__(self, name: Optional[str] = None, calibration: Optional[Mapping[str, AxisCalibration]] = None):
        self.name = name
        self.calibration: Dict[int, AxisCalibration] = {
            code(axis_name): axis_calibration for axis_name, axis_calibration in (calibration or {}).items()
        }
        # States are immutable and replaced whole, so readers never see half a frame
        self._state = JoystickState()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Only touched by the reader thread
        self._absinfo = {}
        self._raw: Dict[int, int] = {}
        self._pressed = set()
        self._dropped = False

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join()

    def state(self) -> JoystickState:
        return self._state

    def _run(self):
        waiting = False
        ignored: List[str] = []
        while not self._stop_event.is_set():
            device = find_joystick(self.name)
            if device is None:
                if not waiting:
                    print("Please connect your joystick")
                    if glob.glob("/dev/input/event*") and not evdev.list_devices():
                        print("No permission to read input devices. Run: sudo usermod -aG input $USER, then log in again")
                    waiting = True
                if self.name is not None:
                    # Any joystick plugged in has the wrong name, e.g. an F310
                    # with the switch on its back set to D instead of X
                    names = joystick_names()
                    if names and names != ignored:
                        print(f"Ignoring {', '.join(names)}, JOYSTICK_NAME in joystick_config.py is {self.name!r}")
                    ignored = names
                self._stop_event.wait(RECONNECT_INTERVAL)
                continue

            waiting = False
            ignored = []
            try:
                self._read(device)
            except OSError as e:
                print(f"Joystick disconnected: {e}")
            except Exception:
                # Never let a bug here leave the last stick position latched
                traceback.print_exc()
            finally:
                self._state = JoystickState()
                device.close()
            self._stop_event.wait(RECONNECT_INTERVAL)

    def _read(self, device):
        self._absinfo = dict(device.capabilities(absinfo=True).get(ecodes.EV_ABS, []))
        self._dropped = False
        self._sync(device)
        self._publish(device)
        self._print_connected(device)

        while not self._stop_event.is_set():
            readable, _, _ = select.select([device.fd], [], [], READ_TIMEOUT)
            if not readable:
                continue
            try:
                for event in device.read():
                    self._handle_event(device, event)
            except BlockingIOError:
                pass  # woke up with nothing to read

    def _handle_event(self, device, event):
        if event.type == ecodes.EV_SYN:
            if event.code == ecodes.SYN_DROPPED:
                # The kernel's buffer overflowed and events were lost. Ignore
                # the rest of this frame, then re-read the whole device.
                self._dropped = True
            elif event.code == ecodes.SYN_REPORT:
                if self._dropped:
                    self._dropped = False
                    self._sync(device)
                self._publish(device)
        elif self._dropped:
            pass  # rest of a frame that lost events, _sync replaces it
        elif event.type == ecodes.EV_ABS and event.code in self._absinfo:
            self._raw[event.code] = event.value
        elif event.type == ecodes.EV_KEY:
            if event.value:  # 1 is pressed, 2 is autorepeat
                self._pressed.add(event.code)
            else:
                self._pressed.discard(event.code)

    def _sync(self, device):
        """Reads the current state straight from the device instead of from events."""
        self._raw = {axis: device.absinfo(axis).value for axis in self._absinfo}
        self._pressed = set(device.active_keys())

    def _publish(self, device):
        self._state = JoystickState(
            connected=True,
            name=device.name,
            axes={
                axis: normalize(raw, self._absinfo[axis], self.calibration.get(axis, AxisCalibration()))
                for axis, raw in self._raw.items()
            },
            raw_axes=dict(self._raw),
            pressed=frozenset(self._pressed),
        )

    def _print_connected(self, device):
        print(f"Joystick connected: {device.name} ({device.path}, {device.info.vendor:04x}:{device.info.product:04x})")
        for axis, info in sorted(self._absinfo.items()):
            print(f"  {code_name(ecodes.EV_ABS, axis):<12} {info.min}..{info.max} (flat {info.flat})")
        buttons: List[int] = device.capabilities(absinfo=False).get(ecodes.EV_KEY, [])
        print(f"  buttons: {' '.join(code_name(ecodes.EV_KEY, button) for button in buttons)}")
        for axis in self.calibration:
            if axis not in self._absinfo:
                print(f"  WARNING: {code_name(ecodes.EV_ABS, axis)} is in joystick_config.py but this device doesn't have it")
