from otgw import OTGW
from tcp_client import TcpClient
import logging

logging.basicConfig(level=logging.DEBUG)


otgw = OTGW()

otgw.sendCommand("HW=12")

for line in open('test-data/baxi-roca2.txt'):
    operation = otgw.processLine(line)
    if operation:
        print(operation)