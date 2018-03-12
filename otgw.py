import logging
import re
from collections import deque
import time

log = logging.getLogger(__name__)


class OTGW:

    class Message:
        class MessageLine:
            def flags_converter(val):
                return "{0:b}".format(val)

            def float_converter(val):
                return round(val / float(256), 2)

            def int_converter(val):
                return val

            openthermIds = {
                0: ("status", flags_converter,),
                1: ("control_setpoint", float_converter,),
                9: ("remote_override_setpoint", float_converter,),
                14: ("max_relative_modulation_level", float_converter,),
                16: ("room_setpoint", float_converter,),
                17: ("relative_modulation_level", float_converter,),
                18: ("ch_water_pressure", float_converter,),
                24: ("room_temperature", float_converter,),
                25: ("boiler_water_temperature", float_converter,),
                26: ("dhw_temperature", float_converter,),
                27: ("outside_temperature", float_converter,),
                28: ("return_water_temperature", float_converter,),
                56: ("dhw_setpoint", float_converter,),
                57: ("max_ch_water_setpoint", float_converter,),
                116: ("burner_starts", int_converter,),
                117: ("ch_pump_starts", int_converter,),
                118: ("dhw_pump_starts", int_converter,),
                119: ("dhw_burner_starts", int_converter,),
                120: ("burner_operation_hours", int_converter,),
                121: ("ch_pump_operation_hours", int_converter,),
                122: ("dhw_pump_valve_operation_hours", int_converter,),
                123: ("dhw_burner_operation_hours", int_converter,)
            }
            openthermTypes = {
                0: "Read-Data     ",
                1: "Write-Data    ",
                2: "Invalid-Data  ",
                3: "-reserved-    ",
                4: "Read-Ack      ",
                5: "Write-Ack     ",
                6: "Invalid-Ack   ",
                7: "Unknown-DataId"
            }
            def __init__(self, line, src, msgType, dataId, data):
                self.line = line.rstrip()
                self.src = src
                self.msgType = msgType
                self.dataId = dataId
                self.data = data
                self.msgTypeName = self.openthermTypes[self.msgType]
                if self.dataId in self.openthermIds:
                    dataIdName, converter = self.openthermIds[self.dataId]
                    self.dataIdName = dataIdName;
                    self.value = converter(val = self.data)
                else:
                    self.dataIdName = "Unknown"
                    self.value = data
            def __repr__(self):
                return "MessageLine ({}): {} {} {} ({}) {}".format(self.line, self.src, self.msgTypeName, self.dataIdName, self.dataId, self.value)

        messageParser = re.compile(r'^(?P<source>[BART])(?P<type>[0-9A-F])(?P<res>[0-9A-F])(?P<id>[0-9A-F]{2})(?P<data>[0-9A-F]{4})$')
        dataId = None
        thermostatSrc = None # T
        boilerDst = None # R
        boilerSrc = None # B
        thermostatDst = None # A
        srcValue = None
        dstValue = None
        ready = False
        msg = None
        def hex_int(self, hex):
            return int(hex, 16)
        def processLine(self, msgLine):
            info = self.messageParser.match(msgLine)
            if info is None:
                return False
            (src, msgType, nop, dataId, data) = map(lambda f, d: f(d),
                (str, lambda _: self.hex_int(_) & 7, self.hex_int, self.hex_int, self.hex_int),
                info.groups())
            messageLine = self.MessageLine(msgLine, src, msgType, dataId, data)

            if self.dataId != None and self.dataId != messageLine.dataId:
                self.ready = True
                if self.thermostatSrc and self.thermostatSrc.dataIdName != "Unknown":
                    self.msg = self.thermostatSrc.dataIdName
                return False #it's not from this message line

            self.dataId = messageLine.dataId

            if messageLine.src == 'T':
                self.thermostatSrc = messageLine
            elif messageLine.src == 'R':
                self.boilerDst = messageLine
            elif messageLine.src == 'B':
                self.boilerSrc = messageLine
            elif messageLine.src == 'A':
                self.thermostatDst = messageLine

            return True

        def __repr__(self):
            if self.boilerDst:
                return "Message:\n\t{}\n\t{}\n\t{}\n\t{}".format(self.thermostatSrc, self.boilerDst, self.boilerSrc, self.thermostatDst)
            else:
                return "Message:\n\t{}\n\t{}".format(self.thermostatSrc, self.boilerSrc)



    class Command:
        commandErrors = {
            "NG": "No Good",
            "SE": "Syntax Error",
            "BV": "Bad Value",
            "OR": "Out of Range",
            "NS": "No Space",
            "NF": "Not Found",
            "OE": "Overrun Error",
        }
        command = None
        sent = False
        success = False
        result = None
        error = None
        processed = False
        def __init__(self, commandLine):
            self.command = commandLine.rstrip()
            self.commandWord = commandLine.split("=")[0]
        def processLine(self, msgLine):
            if self.sent and msgLine.startswith(self.commandWord+":"):
                self.result = msgLine.rstrip()
                self.success = True
                self.processed = True
                return True
            if self.sent and msgLine.rstrip() in self.commandErrors.keys():
                self.result = msgLine.rstrip()
                self.success = False
                self.error = self.commandErrors[msgLine.rstrip()]
                self.processed = True
                return True
            return False

        def __repr__(self):
            return "Command ({})\n\tResult: {}\n\tError:{}".format(self.command, self.result, self.error)


    commandQueue = deque([])
    lastCommand = None

    def send_command(self, command):
        log.info("Queueing command: '{}'".format(command))
        self.commandQueue.append(self.Command(command))

    lastMessage = Message()
    seCount = 0

    def processLine(self, line):

        #process message
        processed = self.lastMessage.processLine(line)
        if self.lastMessage.ready: #message ready
            readyMessage = self.lastMessage
            self.lastMessage = self.Message()
            processed = self.lastMessage.processLine(line)
            log.debug(readyMessage)
            if readyMessage.thermostatSrc: # prevent first not full message
                return readyMessage

        #process command
        if not processed and self.lastCommand:
            processed = self.lastCommand.processLine(line)
            if self.lastCommand.processed:
                readyCommand = self.lastCommand
                self.lastCommand = None
                if (not readyCommand.success) and readyCommand.result == "SE" and self.seCount < 3:
                    self.seCount = self.seCount + 1
                    self.sendCommand(readyCommand.commandLine)
                    log.warning("Repeat command ({}): {}".format(self.seCount, readyCommand.commandLine))
                else:
                    self.seCount = 0
                return readyCommand

        if (not self.lastCommand) and self.commandQueue.__len__() > 0:
            self.lastCommand = self.commandQueue.pop()
            return self.lastCommand

        if self.lastCommand and self.lastCommand.sent and time.time() - self.lastCommand.sent > 2 :
            log.warning("No response in 2 sec for command: {}. Repeating.".format(self.lastCommand.command))
            self.lastCommand.sent = False
            return self.lastCommand

        if not processed and len(line.rstrip()) > 0:
            log.warning("Unsupported message: '{}'".format(line.rstrip()))

