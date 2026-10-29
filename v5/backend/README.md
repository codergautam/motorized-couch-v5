# just one more git repo bro i swear

## how to install

1. cd into this repo
2. Install uv: https://docs.astral.sh/uv/getting-started/installation/#standalone-installer
3. run `uv run main.py`

## joystick

Set up for a Logitech F310 gamepad, driven like a racing game. **Put the switch on the back on X**, on D the couch ignores it.

| control | does |
| --- | --- |
| RT | gas, deeper is faster |
| LT | brake, letting go of the gas without it slows down gently |
| right stick | steer |
| d-pad up / down | shift to drive / reverse, only while stopped. Reverse is capped at chill speed |
| d-pad left / right | step through park, neutral, chill, standard, sport, like on the screen. Right after sport goes back to park. Above 2 mph it won't drop into neutral or wrap around to park, brake first |
| LB | horn (TODO) |

The face buttons (A, B, X, Y) and Start do nothing.

Any other USB joystick or gamepad works too, it's read straight from Linux evdev (`joystick.py`). To set up a new one:

1. plug it in and run `uv run joystick_probe.py`
2. wiggle the stick and mash buttons, it prints the names the couch sees (`ABS_Y`, `BTN_THUMB`, ...)
3. put those names in `joystick_config.py`

If the probe lists no devices, the user isn't allowed to read them: `sudo usermod -aG input $USER`, then log in again.

The couch won't drive until the gas is released and the stick centered after picking a drive mode, and if the joystick is unplugged it brakes to a stop, goes to park and shifts back to drive.

## simulator

Try the controls without risking anyone: `uv run simulator.py`. It runs the real control loop and dashboard with simulated motors, and a second window shows where the couch would go from above and exactly what each motor would be told. Works on a Windows laptop (F310 switch on X) and on the Pi, where it reads the joystick exactly like the couch does, so it's a dress rehearsal with the motors left out.

## other materials

- odrive installation guide: https://docs.odriverobotics.com/v/latest/interfaces/odrivetool.html
- use torque control, which automatically limits velocity too: https://docs.odriverobotics.com/v/latest/manual/control.html#:~:text=For%20safety%20reasons%2C%20the%20torque%20mode%20velocity%20limiter%20is%20enabled%20by%20default.%20This%20works%20by%20reducing%20the%20torque%20of%20the%20motor%20according%20to%20vel_limit%20and%20vel_gain%2C%20as%20shown%20below.%20Please%20note%20that%20with%20the%20default%20settings%2C%20torque%20will%20be%20limited%20even%20at%200%20rpm.

