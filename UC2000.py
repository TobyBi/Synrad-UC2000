"""
.. include:: ./README.md
"""

import time

# =============================================================================
# Parameters for UC2000 object
# =============================================================================

_PERCENT_TRANSFORMS =    {63: 62.5}
# Transforming PWM percent incompatible without checksum to compatible ones
SHOT_TIME_RANGE =       [50, 10000]
"""Valid shot time range."""
MIN_LASE_PERCENT =      2
"""Minimum percent required for laser to be considered OFF to material without
turning the Command signal OFF."""

class UC2000Controller:
    """
    An interface to SYNRAD 48 series CO2 lasers through UC-2000 controller.

    Communication to the UC-2000 controller from a host using REMOTE
    settings are facilitated through the Serial RS-232 protocol and port.

    Parameters
    ----------
    model : {25, 50}
        SYNRAD 48 series laser model number, indicates the maximum
        optical power output.
    open_labjack : LabJack object
        A LabJack object to transmit messages to the UC-2000,
        by default ``False``.

    Attributes
    ----------
    PARAMETER_NAME_hist : list
        Entire history of previous PARAMETER_NAME from instantiation.

    Notes
    -----
    Pins 2, 3, and 5 of a serial port are used for receive, transmit, and
    ground respectively.
    The host serial port configuration must be
        Baud rate       9600
        Data bits       8 bits
        Parity          None
        Stop bits       1 bit
        Flow control    None

    For further details please refer to:
    https://synrad.com/en/products/accessories/uc-2000

    ``Messages`` are sent to the UC-2000 from the host via a DAQ, in this case
    a LabJack T4/T7 is used. However, any source that can produce RS-232
    asynchronous communication can be used. If a Labjack object or no other
    DAQ is provided then the UC-2000 only stores messages.

    TODO: LUA scripting - call script to improve timings
    TODO: gate pull-up/down, SYNRAD doesn't know whether gate or comamnd signal activate lasing is faster. Trial and error?

    TODO: receiving communication from the labjack... or using the UC2000 response
        if check_ack:
            daq_response = daq_stats["response"]

            if not isinstance(daq_response, list):
                daq_response = [daq_response]

            if UC2000_RESPONSE["ack"] in daq_response:
                self.laser_controller.set_any(setting, option)
                gui_message = "\"{0}\" has changed to \"{1}\"".format(setting, option)
                action = "continue"
                outcome = option
            elif UC2000_RESPONSE["nak"] in daq_response:
                gui_message = "\"{0}\" remains unchanged as {1} because UC2000 didn't accept the message".format(setting, prev)
                action = "previous"
                outcome = prev
            else:
                gui_message = "Setting \"{0}\" remains unchanged as {1} because there has been no response from UC2000".format(setting, prev)
                action = "previous"
                outcome = prev
        else:
            self.laser_controller.set_any(setting, option)
            gui_message = "Setting \"{0}\" has changed to \"{1}\"".format(setting, option)
            action = "continue"
            outcome = option

    TODO: test with slightly longer wait time between asynch communications
    TODO: can send remote status byte inbetween start and end transmission byte of any other
    command - maybe use to check option on laser

    Examples
    --------
    >>> laser = UC2000Controller(model=25)
    >>> with laser:
    ...     laser.percent = 20
    ...     laser.lase = True
    ...     laser.percent = 0
    ...     laser.lase = False

    Demonstration of the .percent and .lase commands
    """

    percent_step = 0.5
    """Minimum step size of PWM percent."""

    _default = {
        "pwm_freq":         20,   # Higher PWM frequency means lower ripple in optical beam response
        "gate_logic":       "up",
        "max_pwm":          95,
        "lase_on_power_up": False,
        "mode":             "manual", # this will be different for reflow and laser machining
        "lase":             False,
        "percent":          0,
    }
    # TODO: update RC params style?
    # TODO: set defaults list into controller as argument for changable settings

    def __init__(self, model: int, open_labjack=False):
        """Inits a UC2000 object."""
        self.model = model

        self._open_labjack = open_labjack

        self.pwm_freq_hist = [None]
        self.gate_logic_hist = [None]
        self.max_pwm_hist = [None]
        self.lase_on_power_up_hist = [None]
        self.mode_hist = [None]
        self.lase_hist = [None]
        self.percent_hist = [None]
        self.checksum_hist = []
        self.shot_time_hist = []

        # Assumes that Checksum mode is enabled...
        # and why would we not use checksum mode anyways
        self.checksum = True

        self.reset()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        if exc_type is KeyboardInterrupt:
            print("Laser process stopped by user")
            self.percent = 0
            self.lase = False
            # returning False because we want to allow nested with statements
            # above the stack to also use their __exit__ which turns the laser
            # off and low set percent.
            return False

        # turn it down anyways
        self.percent = 0
        self.lase = False
        return exc_type is None

    @property
    def lase(self):
        """Return lase state."""
        return self._lase

    @lase.setter
    def lase(self, state: bool):
        """
        Set lase state to either True or False.

        Parameters
        ----------
        state : bool
            New set lase state.

        Notes
        -----
        Lase state is controlled by a Command signal for LOW (0 - 0.5V DC)
        and HIGH (3.5 - 5V DC).

        When the Command signal is low for >200us, the UC-2000 always supplies
        laser with 5kHz, 1us tickle pulse that pre-ionises the laser gas to
        just below lasing threshold. Any increase in pulse width causes
        emission as enough energy is added to the plasma.

        If a labjack is connected, then a LASE message will be sent to the
        UC2000.
        """
        self._lase = state
        self.lase_hist.append(state)

        # if the new option is the same as before don't send changes to labjack
        if (self.lase_hist[-2] != state) and self._open_labjack:
            msg = Message("lase", state, self.checksum).message_bytes
            self._open_labjack.asynch.transmit(msg)

    @property
    def percent(self):
        """Return laser percent, representing the PWM signal duty cycle percentage."""
        return self._percent

    @percent.setter
    def percent(self, per: float):
        """
        Set laser percent (PWM signal duty cycle percentage), limited to
        between 0 and 95/99% in steps of 0.5%.

        Parameters
        ----------
        per : float
            New PWM duty cycle percentage, in seteps of 0.5%

        Notes
        -----
        The laser percent defaults to previous percent if new percent is
        outside of the permitted range. If self.checksum flag is True, then the
        set laser percent cannot be 63% defaults to 62.5% instead.

        The PWM signal duty cycle controls how much of the Command signal's
        pulse is HIGH. When the Command signal is HIGH, the laser RF amplifiers
        are HIGH and this increases the optical output power.

        If a labjack is connected, then a SET message will be sent to the
        UC2000.
        """
        per = self._pwm_percent_limits(per)
        self._percent = per
        self.percent_hist.append(per)

        if self.percent_hist[-2] != per and self._open_labjack:
            msg = Message("percent", per, self.checksum).message_bytes
            self._open_labjack.asynch.transmit(msg)

    @property
    def pwm_freq(self):
        """Return laser PWM frequency."""
        return self._pwm_freq

    @pwm_freq.setter
    def pwm_freq(self, freq: int):
        """
        Set laser PWM frequency to either 5, 10, or 20kHz.

        Parameters
        ----------
        freq : {5, 10, 20}
            New laser percent.

        Notes
        -----
        The PWM frequency of the Command signal, where the laser optical output
        follows the Command signal with a rise/fall time of 75-150us. A higher
        PWM frequency means the laser output response has less ripple and at
        20kHz the laser output is nearly CW with small ripple.

        If a labjack is connected, then a SETUP message will be sent to the
        UC2000.
        """
        self._pwm_freq = freq
        self.pwm_freq_hist.append(freq)

        if self.pwm_freq_hist[-2] != freq and self._open_labjack:
            msg = Message("pwm_freq", freq, self.checksum).message_bytes
            self._open_labjack.asynch.transmit(msg)

    @property
    def gate_logic(self):
        """Return gate pull up/down status."""
        return self._gate_logic

    @gate_logic.setter
    def gate_logic(self, pull: str):
        """
        Set gate pull up/down status to either pull "up" or "down".

        Parameters
        ----------
        pull : {"up", "down"}
            New gate pull status.

        Notes
        -----
        Gate pull up indicates that the laser will fire without a gate signal.
        This means the UC-2000 connects an internal resistor between the gate
        and command signal.

        Gate pull down means the laser will fire when the gate signal is HIGH
        and the command signal is HIGH. A gate signal is supplied to the Gate
        BNC input and is either logic LOW (0 - 0.9V DC) or HIGH (2.8 - 5 V DC).
        Now, the tickle pulse and command signals are determined by the
        Gating amplitude.

        Note: PWM and gate pulses are not asynchronous, the edges of both
        pulses are not synchronised.

        Input impedence: 50 kOhms
        Gate On Time, min: 3.5us (10ms in closed loop mode)/

        If a labjack is connected, then a SETUP message will be sent to the
        UC2000.
        """
        self._gate_logic = pull
        self.gate_logic_hist.append(pull)

        if self.gate_logic_hist[-2] != pull and self._open_labjack:
            msg = Message("gate_logic", pull, self.checksum).message_bytes
            self._open_labjack.asynch.transmit(msg)

    @property
    def max_pwm(self):
        """Return the maximum PWM perentage or maximum duty cycle time."""
        return self._max_pwm

    @max_pwm.setter
    def max_pwm(self, per: int):
        """
        Set the maximum PWM percentage of the Command signal.

        Parameters
        ----------
        per : {95, 99}
            New max PWM percentage.

        Notes
        -----
        Synrad lasers have max PWM percentage of 95% by default to increase
        longevity of lasers as greater than 95% increases heat load and "may
        cause thermal instability and optical degradation."

        If a labjack is connected, then a SETUP message will be sent to the
        UC2000.
        """
        self._max_pwm = per
        self.max_pwm_hist.append(per)

        if self.max_pwm_hist[-2] != per and self._open_labjack:
            msg = Message("max_pwm", per, self.checksum).message_bytes
            self._open_labjack.asynch.transmit(msg)

    @property
    def lase_on_power_up(self):
        """Return lase on power-up status."""
        return self._lase_on_power_up

    @lase_on_power_up.setter
    def lase_on_power_up(self, pwr: bool):
        """
        Set lase on power-up status to either True or False.

        Parameters
        ----------
        pwr : bool
            New lase on power-up setting.

        Notes
        -----
        If the lase on power-up status is ON, then the UC-2000 controller will
        send a lase signal immediately when the power is turned on. Used only
        when access to UC-2000 controller is limited.

        If a labjack is connected, then a SETUP message will be sent to the
        UC2000.
        """
        self._lase_on_power_up = pwr
        self.lase_on_power_up_hist.append(pwr)

        if self.lase_on_power_up_hist[-2] != pwr and self._open_labjack:
            msg = Message("lase_on_power_up", pwr, self.checksum).message_bytes
            self._open_labjack.asynch.transmit(msg)

    @property
    def mode(self):
        """Return UC-2000 operating mode."""
        return self._mode

    @mode.setter
    def mode(self, mode_type: str):
        """
        Set UC-2000 operating mode to 5 possible choices.

        Parameters
        ----------
        mode_type : {"manual", "anc", "anv" "man_closed", "anv_closed"}
            New operating mode.

        Notes
        -----
        MANUAL ("manual")
        Laser output power is adjusted by the PWM command signal duty cycle
        percentage.

        ANC ("anc")
        Laser power controlled by external 4-20mA current loop. PWM duty cycle
        changes proportionally to applied current.

        ANV ("anv")
        Laser power controlled by external analog 0-10V source where the duty
        cycle is proportional to external voltage.

        MAN. CLOSED ("man_closed")
        Closed loop power is ensured by Closed Loop Stablization Kit which
        regulates power stability to within +/-2% of the setpoint. Closed loop
        settling time is typically 2ms after setpoint change. The recommended
        lower and upper control range is 20-80% PWM duty cycle percent.

        ANV CLOSED ("anv_closed")
        Similar to MAN. CLOSED except an external analog voltage is stabilised.

        If a labjack is connected, then a MODE message will be sent to the
        UC2000.
        """
        self._mode = mode_type.lower()
        self.mode_hist.append(mode_type)

        if self.mode_hist[-2] != mode_type and self._open_labjack:
            msg = Message("mode", mode_type, self.checksum).message_bytes
            self._open_labjack.asynch.transmit(msg)

    @property
    def checksum(self):
        """Return checksum protocol use."""
        return self._checksum

    @checksum.setter
    def checksum(self, check: bool):
        """
        Set checksum protocol used for commands sent through the RS-232 protocol.

        Parameters
        ----------
        check : bool
            New checksum enable or disable option.

        Notes
        -----
        Only changes the message sent by Python and not the message sent by the
        UC-2000. That setting must be physcially changed on the controller.

        Enabled checksum means messages are sent with a final checksum byte
        used to better handle errors with serial communication. Details on the
        checksum byte and other message formats can be found in the
        "Message.py" class.
        """
        self._checksum = check
        self.checksum_hist.append(check)

    @property
    def max_power(self):
        """Return estimated maximum output optical power of the laser based on the model and the max_pwm setting in Watts."""
        est_max_power = self.model * self.max_pwm / 100
        return est_max_power

    @property
    def power(self):
        """Return current estimated output optical power of the laser in Watts."""
        return self.model * self.percent / 100

    def reset(self):
        """Reset all UC-2000 settings to default."""
        # TODO: have reset flag such that it forces all the bottom changes
        self.pwm_freq = self._default["pwm_freq"]
        self.gate_logic = self._default["gate_logic"]
        self.max_pwm = self._default["max_pwm"]
        self.lase_on_power_up = self._default["lase_on_power_up"]

        self.mode = self._default["mode"]
        self.lase = self._default["lase"]
        self.percent = self._default["percent"]    # in percent

    def _pwm_percent_limits(self, limit_per: float):
        """
        Limits input PWM percent to (0, 95/99) and converting '63%' to '62.5%'.

        If input is larger than current max PWM setting then reset to
        previous PWM percent.

        Parameters
        ----------
        limit_per : float
            Input percent.

        Returns
        -------
        setpoint : float
            Actual valid setpoint.
        """
        # Check if the input percent is an int or float
        try:
            limit_per = float(limit_per)
        except (ValueError, TypeError):
            # make new error here?
            raise ValueError("Not a valid input percent")

        if limit_per > self.max_pwm:
            # Set to previous percent
            setpoint = self.percent
        elif limit_per < 0:
            # Set to 0 if negative
            setpoint = 0
        else:
            # Changes setpoint to be multiple of 0.5
            setpoint = self.percent_step * round(limit_per / self.percent_step)

        # FIXME: only change this for if checksum if False
        # Changes setpoint from 63 to 62.5% if checksum mode is disabled
        if setpoint in PERCENT_TRANSFORMS:
            setpoint = PERCENT_TRANSFORMS[setpoint]

        # TODO: make this to logging instead?
        print("Setpoint is {0}%".format(setpoint))
        return setpoint

    @staticmethod
    def _shot_time_limits(shot: float):
        """
        Limits input shot time to between 50ms to 10s.

        If oustide the permitted range then the shot time is 50ms.

        Parameters
        ----------
        shot : float
            Input shot time in ms.

        Returns
        -------
        float
            Valid shot time in ms.

        Notes
        -----
        Shot time is the time between the laser ON and OFF state, which can be
        either:
            - Turning the command signal between ON and OFF
            - Setting the PWM command signal percent to the minimum lase value
            - Switching the Gate signal between HIGH and LOW

        Currently limited by communication speed between Python script and
        UC-2000 controller.
        """
        try:
            shot = float(shot)
        except (ValueError, TypeError):
            # make new error here?
            raise ValueError("Not a valid shot time")

        if shot < min(SHOT_TIME_RANGE):
            return min(SHOT_TIME_RANGE)
        elif shot > max(SHOT_TIME_RANGE):
            return min(SHOT_TIME_RANGE)
        else:
            return shot

    def shoot(self, shot_percent: float, shot_time: float, num_shots: int):
        """
        Shoots a laser shot by using PWM percent sequence of LOW, HIGH, LOW.

        Currently, the low laser percent is 3% as this doesn't affect the
        silica glass rods we are using, however, the option can be set in the
        script above.

        Parameters
        ----------
        shot_percent : float
            PWM laser percent.
        shot_time : float
            Time of shot in ms.
        num_shots : int
            Number of consecutive shots.

        Returns
        -------
        dict
            Dict containing average interval time, total time, and any response
            from UC-2000.

        Notes
        -----
        Shot time can be guaranteed but time between shots might be less
        accurate.

        If shooting more than once, the time between shots is the same time as
        the shot time.

        Examples
        --------
        >>> laser = UC2000Controller(model=25)
        >>> with laser:
        ...     laser.shoot(10, 500, 2)

        Fires 2 shots for 500ms at 10% PWM duty cycle percent.
        """
        shot_time = self._shot_time_limits(shot_time)
        # Convert shot_time to microseconds

        # operations inside the interval.. Labjack interval ensures that the
        # percent should be this for the selected shot_time
        def ops_inside(idx):
            if idx % 2 == 0:
                self.percent = shot_percent
            elif idx % 2 == 1:
                self.percent = MIN_LASE_PERCENT
            return idx + 1, ""

        # operations outside the interval occur as soon as the host sends the
        # command to Labjack
        def ops_outside(idx):
            self.percent = MIN_LASE_PERCENT
            return idx, ""

        self.percent = MIN_LASE_PERCENT
        self.lase = True
        if self._open_labjack:
            # Interval_number is 2*num_shots - 1 because the operations outside
            # end the shot so need odd number of iterations to ensure correct
            # number of shots
            self._open_labjack.add_interval(int(shot_time*1e3), 2*num_shots - 1)
            interval_metrics = self._open_labjack.interval.start_interval(
                operations_inside=ops_inside,
                operations_outside=ops_outside
                )
        else:
            interval_metrics = {}
        self.percent = MIN_LASE_PERCENT
        self.lase = False
        self.shot_time_hist += [shot_time]*num_shots
        return interval_metrics


# =============================================================================
# Parameters for Message object
# =============================================================================

# Dict for converting between command name and byte
_UC2000_COMMAND_BYTES = {
    "pwm_freq": {
        5: 0x77,
        10: 0x78,
        20: 0x7a
    },
    "gate_logic": {
        "up": 0x7a,
        "down": 0x7b
    },
    "max_pwm": {
        95: 0x7c,
        99: 0x7d,
    },
    "lase_on_power_up": {
        True: 0x30,
        False: 0x31
    },
    "mode" : {
        "manual": 0x70,
        "anc": 0x71,
        "anv": 0x72,
        "man_closed": 0x73,
        "anv_closed": 0x74,
    },
    "lase": {
        True: 0x75,
        False: 0x76,
    },
}

class Message():
    """
    REMOTE Message sent to UC-2000 on REMOTE mode through RS-232 serial
    port.

    Parameters
    ----------
    command : {"pwm_freq", "gate_logic", "max_pwm", "lase_on_power_up", "mode", "lase", "percent", "status_request"}
        Command name, will be converted to command byte.
    data : float
        Data for PWM (or SET for closed loop) command.
    checksum : bool
        Checksum protocol mode.

    Notes
    -----
    There are 5 types of messages with different formats sent;
        Setup ("pwm_freq", "gate_logic", "max_pwm", "lase_on_power_up")
        Mode ("mode")
        PWM (or closed loop SET) ("percent")
        Lase ("lase")
        Status Request

    Setup Mode, and Lase commands have the byte sequence:
        STX<Command><Checksum>
        STX - start transmission byte.
        The checksum byte is the one's compliment of the Command byte.

    PWM (or SET) command byte sequence:
        STX<Command><Data Byte><Checksum>
        Data byte is the PWM percentage multipled by 2, converted into hex.
        The checksum byte is the adding without carry between command and
        data byte and then performing the one's compliment.

    Response from Setup, Mode, Lase, and PWM is either ACK (0xAA) or NAK
    (0x3F). A NAK is sent if there is no valid command or checksum byte
    sent within 1s of STX byte or if the checksum byte is wrong.

    Status Request:
        Single byte to tell UC-2000 to report it's status.

    Response from Status Request is
        ACK<Status Byte1><Status Byte2><PWM Byte><Power Byte><Checksum>
        Refer to the UC-2000 manual for futher details about the contents
        of the response bytes. Currently not using so not as important.

    TODO: include parsing response byte from UC-2000

    Examples
    --------
    >>> message = Message("percent", 10, False)
    >>> message.message_bytes()
    [126, 127, 20]

    Create message for setting PWM percent to 10%.

    >>> message = Message("lase", True, False)
    >>> message.message_bytes()
    [126, 127, 117]

    Create message for turning on command signal.
    """
    _start_byte = 0x5b
    # (STX) First byte sent to initialise communication, not needed when sending request.
    _status_request_byte = 0x7e
    _set_percent_byte = 0x7f

    def __init__(self, command: str, data, checksum: bool):
        """Inits a ``Message`` object."""
        self.command = command
        """Command to perform"""
        self.checksum = checksum
        """Checksum protocol mode."""
        self.data = data
        """Data for PWM (or SET for closed loop) command."""

    @property
    def message_bytes(self):
        """
        Creates and returns REMOTE message byte sequence.

        Returns
        -------
        message : list of int
            The message sequence containing the start byte, command byte,
            [data byte (optional)], and checksum (optional)
        """
        if self.command in _UC2000_COMMAND_BYTES.keys():
            command_byte = _UC2000_COMMAND_BYTES[self.command][self.data]

            message = [self._start_byte, command_byte]

            if self.checksum:
                # without data, the checksum is the one's compliment of the
                # command byte
                checksum_byte = ~command_byte & 0xff
                message.append(checksum_byte)

        elif self.command == "percent":
            try:
                message = [
                    self._start_byte, self._set_percent_byte, int(2*self.data)]
            except ValueError:
                raise ValueError(
            "Type of data is invalid. Needs to be float or int.")

            if self.checksum:
                # with data, the checksum is the addition without carry of the
                # command and data byte and then one's complimented
                checksum_byte = (
                    ~self.add_no_carry(
                        self._set_percent_byte, self.data) & 0xff
                    )
                message.append(checksum_byte)

        elif self.command == "status_request":
            message = [self._status_request_byte]

        else:
            raise ValueError("Command is not recognised by UC-2000")

        return message

    @staticmethod
    def add_no_carry(*args):
        """
        Addition without carry; addition is not carried to the next decimal up.

        Parameters
        ----------
        *args : iterable (not string)
            Iterate of ints to add without carry.

        Returns
        -------
        final_sum : int
            the result...

        Examples
        --------
        >>> add_no_carry(1, 1)
        2

        >>> add_no_carry(1, 18)
        19

        >>> add_no_carry(1, 19)
        10

        The '10' is not carried over to the next decimal.
        """
        num_digits = []

        for arg in args:
            num_digits.append(len(str(arg)))

        max_digits = max(num_digits)
        # list comprehension way
        # max_digits = max([len(str(arg)) for arg in args])
        final_sum = 0

        for pwr in range(1, max_digits + 1): # iterate through ea decimal
            result_no_carry = 0
            for arg in args:
                if len(str(arg)) >= pwr:
                    # modulus sets the current decimal as the most significant
                    # decimal
                    # floor div selects the most significant decimal
                    result_no_carry += arg % 10**pwr // 10**(pwr - 1)

            # list comprehension way
            # result_no_carry = sum([arg % 10**pwr // 10**(pwr - 1) for arg in args if len(str(arg)) >= pwr])

            # final_sum = str(result_no_carry % 10) + final_sum
            final_sum += result_no_carry % 10

        return int(final_sum)
