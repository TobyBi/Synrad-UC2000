# Synrad-UC2000

Wrapper to communicate with a Synrad [UC-2000 Universal Laser Controller](https://synrad.com/en/products/accessories/uc-2000) through the REMOTE port. A UC-2000 controller controls Synrad [48 Series CO<sub>2</sub> lasers](https://synrad.com/en/products/lasers/48-series).



## Requirements
- Python >= 3.8.5
- [OPTIONAL] If using `Synrad-UC2000` with a LabJack, then the `LabJack-DAQ` module is required. Please visit the [repository](https://github.com/TobyBi/LabJack-DAQ) for further installation guidelines.

Only written and tested with LabJack DAQ control and 48-2 and 48-5 lasers in mind.



## Installation

To install simply clone the git directory using the following commands:

```bash
git clone https://github.com/TobyBi/Synrad-UC2000
```

Move the file `uc2000` to your program location and import it.



## Usage

The main points to interface with the laser and controller are

- `percent` for the % of the PWM width,
- `lase` for the lasing state of the laser, and
- `shoot` which fires a chosen number of shots at a given `percent` and `shot_time` .



The less frequently changed settings of the laser and controller are:

- PWM frequency,
- gate logic,
- max PWM percent,
- controller mode, and
- checksum.



If you are using `lase` and `percent` functions with any other modules that include premature termination of the program, make sure to execute the commands within a [context manager](https://docs.python.org/3/library/contextlib.html) e.g.

```python
laser = UC2000Controller(25)
with laser:
    laser.percent = 10
    laser.lase = True
    
    # Program is blocked
```

If the program is terminated using a `KeyboardInterrupt`, then the laser will always turn off. This is featured directly in the `shoot` function so using the context manager is not required there.

Refer to the [documentation](https://tobybi.github.io/Synrad-UC2000/uc2000.html) for more details.



## TODO

- Lua scripting for better timings
- Default to PySerial without any DAQ