from helpers import add_no_carry

# Start transmission byte (STX)
START_BYTE =            0x5b
STATUS_REQUEST_BYTE =   0x7e
SET_PERCENT_BYTE =      0x7f

UC2000_COMMAND_BYTES = {
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
    def __init__(self, command: str, data, checksum: bool):
        """
        REMOTE Message sent to UC-2000 on REMOTE mode through RS-232 serial 
        port.

        Parameters
        ----------
        command : {"pwm_freq", "gate_logic", "max_pwm", "lase_on_power_up",
                    "mode", "lase", "percent", "status_request"}
            Command byte.
        data : float
            Data for PWM (or SET for closed loop) command.
        checksum : bool
            Checksum protocol mode.

        Attributes
        ----------
        command
        data
        checksum
        message_bytes

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
        self.command = command
        self.checksum = checksum
        self.data = data

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
        if self.command in UC2000_COMMAND_BYTES.keys():
            command_byte = UC2000_COMMAND_BYTES[self.command][self.data]

            message = [START_BYTE, command_byte]

            if self.checksum:
                # without data, the checksum is the one's compliment of the 
                # command byte
                checksum_byte = ~command_byte & 0xff
                message.append(checksum_byte)

        elif self.command == "percent":
            try:
                message = [START_BYTE, SET_PERCENT_BYTE, int(2*self.data)]
            except ValueError:
                raise ValueError("Type of data is invalid. Needs to be float or int.")

            if self.checksum:
                # with data, the checksum is the addition without carry of the 
                # command and data byte and then one's complimented
                checksum_byte = (
                    ~add_no_carry(SET_PERCENT_BYTE, self.data) & 0xff
                    )
                message.append(checksum_byte)

        elif self.command == "status_request":
            message = [STATUS_REQUEST_BYTE]

        else:
            raise ValueError("Command is not recognised by UC-2000")

        return message
