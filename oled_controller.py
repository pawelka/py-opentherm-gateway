import requests
from threading import Thread
import time
from otgw import OTGW
from collections import deque
import logging

log = logging.getLogger(__name__)

class OledController:

    __worker_thread = None
    __dhw = deque([])

    loader = ["/", "-", "\\", "|"]

    def __init__(self, host):
        self.__host = host

    def start(self):
        if self.__worker_thread:
            raise RuntimeError("Already running")
        self.__worker_thread = Thread(target=self.__worker)
        self.__worker_thread.start()

    def on_otgw_message(self, msg):
        if isinstance(msg, OTGW.Message):
            if msg.msg == "dhw_setpoint":
                if msg.boilerSrc:
                    self.__dhw.append((1, "WB: {}".format(msg.boilerSrc.value)))
                else:
                    self.__dhw.append((1, "WB: -   "))
                if msg.thermostatDst:
                    self.__dhw.append((2, "WT: {}".format(msg.thermostatDst.value)))
                else:
                    self.__dhw.append((2, "WT: -   "))
            if msg.msg == "dhw_temperature":
                if msg.boilerSrc:
                    self.__dhw.append((4, "WW: {}".format(msg.boilerSrc.value)))
            if msg.msg == "control_setpoint":
                pass

    def __build_url(self, command):
        return "http://{}/control?cmd={}".format(self.__host, command)

    lastRows = {}

    def __worker(self):
        id = 0
        r = requests.get(self.__build_url("oledcmd,clear"))
        r.status_code
        while True:
            try:
                while len(self.__dhw) > 0:
                    msg = self.__dhw.pop()
                    if (not msg[0] in self.lastRows) or self.lastRows[msg[0]] != msg[1]:
                        self.lastRows[msg[0]] = msg[1]
                        r = requests.get(self.__build_url("oled,{},1,{}".format(msg[0], msg[1])))
                        r.status_code
                r = requests.get(self.__build_url("oled,6,1,       {}".format(self.loader[id])))
                id = (id + 1) % 4
                r.status_code
                time.sleep(1)
            except Exception as e:
                log.error(e)

