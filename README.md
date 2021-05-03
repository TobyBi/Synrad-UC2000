# Synrad UC2000 Controller

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

and then move the file `uc2000.py` to your program location.



## TODO

- Lua scripting for better timings
- Default to PySerial without any DAQ