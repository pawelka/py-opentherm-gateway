import logging
import socket
import time

log = logging.getLogger(__name__)

class TcpClient:

    def __init__(self, host, port):
        self.__host = host
        self.__port = port
        self.__timeout = 5
        self.__opened = False

    def __open(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            log.info("Connecting to {}:{}".format(self.__host, self.__port))
            self._socket.connect((self.__host, self.__port))
            self._socket.settimeout(self.__timeout)
            self.__opened = True
            log.info("Connected to {}:{}".format(self.__host, self.__port))
        except OSError as e:
            log.error("Exception while connecting ({}). Sleep {} sec and retry".format(e, self.__timeout))
            time.sleep(self.__timeout)
            self.__open()

    def __close(self):
        self._socket.close()
        self.__opened = False

    def write(self, data):
        dataToSend="{}\r".format(data.rstrip('\r\n')).encode()
        self._socket.sendall(dataToSend)

    lastData = 0

    def read(self):
        if not self.__opened:
            self.__open()
        try:
            data = self._socket.recv(11).decode()
            if data:
                self.lastData = time.time()

            if not data and (time.time() - self.lastData > self.__timeout):
                log.warning("Data missing reconnecting")
                self.__close()
            return data
        except socket.timeout:
            log.warning("Data timeout reconnecting")
            self.__close()
            return ''

