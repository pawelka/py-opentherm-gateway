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
                if msg.thermostatDst:
                    self.__dhw.append((2, "WT: {}".format(msg.thermostatDst.value)))
            if msg.msg == "control_setpoint":
                pass

    def __worker(self):
        id = 0
        r = requests.get('http://192.168.2.202/control?cmd=oledcmd,clear')
        r.status_code
        while True:
            try:
                while len(self.__dhw) > 0:
                    msg = self.__dhw.pop()
                    r = requests.get('http://192.168.2.202/control?cmd=oled,{},1,{}'.format(msg[0], msg[1]))
                    r.status_code

                r = requests.get('http://192.168.2.202/control?cmd=oled,6,1,       {}'.format(self.loader[id]))
                id = (id + 1) % 4
                r.status_code
                time.sleep(1)
            except Exception as e:
                log.error(e)

