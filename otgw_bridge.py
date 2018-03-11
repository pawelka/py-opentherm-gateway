import logging
import re
from otgw import OTGW
from tcp_client import TcpClient
from threading import Thread
from otgw_bridge_config import config
from oled_controller import OledController
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO)

log = logging.getLogger(__name__)

class OTGWBridge:

    def __init__(self, config):
        self.__otgwClient = TcpClient(config['otgw']['host'], int(config['otgw']['port']))
        self.__otgw = OTGW()
        self.__otgw_worker_thread = None
        self.__config = config
        self.__oled = OledController()

    def run(self):
        if self.__otgw_worker_thread:
            raise RuntimeError("Already running")
        self.__otgw_worker_thread = Thread(target=self.__otgw_worker)
        self.__otgw_worker_thread.start()
        self.__oled.start()
        self.__run_mqtt()

    def __run_mqtt(self):
        def on_mqtt_connect(client, userdata, flags, rc):
            # Subscribe to all topics in our namespace when we're connected. Send out
            # a message telling we're online
            log.info("Connected with result code " + str(rc))
            client.subscribe('{}/#'.format(self.__config['mqtt']['set_topic_namespace']))
            client.publish(
                topic=self.__config['mqtt']['value_topic_namespace'],
                payload="online",
                qos=self.__config['mqtt']['qos'],
                retain=self.__config['mqtt']['retain'])

        mqttc = mqtt.Client("otgw", clean_session=False)
        if self.__config['mqtt']['username']:
            mqttc.username_pw_set(self.__config["mqtt"]["username"], self.__config["mqtt"]["password"])
        mqttc.connect(self.__config["mqtt"]["host"], self.__config["mqtt"]["port"])

        def on_disconnect(client, userdata, rc):
            if rc != 0:
                log.warning("Unexpected MQTT disconnection. Will auto-reconnect")

        mqttc.on_connect = on_mqtt_connect
        mqttc.on_message = self.__on_mqtt_message
        mqttc.on_disconnect = on_disconnect
        mqttc.will_set(
            topic=self.__config['mqtt']['value_topic_namespace'],
            payload="offline",
            qos=self.__config['mqtt']['qos'],
            retain=True)

        self.__mqttc = mqttc
        mqttc.loop_forever()

    def __on_mqtt_message(self, client, userdata, msg):
        log.debug("Received message on topic {} with payload {}".format(msg.topic, str(msg.payload)))
        command_generators = {
            "set/otgw/room_setpoint/temporary": lambda _: "TT={:.2f}".format(float(_)),
            "set/otgw/room_setpoint/constant": lambda _: "TC={:.2f}".format(float(_)),
            "set/otgw/outside_temperature": lambda _: "OT={:.2f}".format(float(_)),
            "set/otgw/hot_water/enable": lambda _: "HW={}".format('1' if _ in self.__true_values else '0'),
            "set/otgw/hot_water/temperature": lambda _: "SW={:.2f}".format(float(_)),
            "set/otgw/central_heating/enable": lambda _: "CH={}".format('1' if _ in self.__true_values else '0'),
        }
        # Find the correct command generator from the dict above
        command_generator = command_generators.get(msg.topic)
        if command_generator:
            # Get the command and send it to the OTGW
            command = command_generator(msg.payload)
            log.info("Sending command: '{}'".format(command))
            self.__otgw.sendCommand(command)

    __true_values = ('True', 'true', '1', 'y', 'yes')

    def __on_otgw_message(self, message):
        for msg in self.__otgw_translate_message(message):
            log.debug("Sending message to topic {} value {}".format(msg[1], msg[2]))
            self.__mqttc.publish(
                topic=msg[1],
                payload=msg[2],
                qos=config['mqtt']['qos'],
                retain=config['mqtt']['retain'])
            # print(message)

    def __otgw_translate_message(self, message):
        def extractBit(value, number):
            rev = value[::-1]
            try:
                return str(rev[number] == "1")
            except:
                return str(False)
        if message.msg and message.boilerSrc and message.thermostatSrc:
            msg = message.msg
            topic = "{}/{}".format(self.__config['mqtt']['value_topic_namespace'], msg)
            value = message.boilerSrc.value

            if msg == "status":
                #value.
                return iter([
                    (msg, "{}/fault".format(topic), extractBit(value, 0)),
                    (msg, "{}/ch_active".format(topic), extractBit(value, 1)),
                    (msg, "{}/dhw_active".format(topic), extractBit(value, 2)),
                    (msg, "{}/flame".format(topic), extractBit(value, 3)),
                ])
            else:
                return iter([(msg, topic, value)])
        else:
            return iter([])

    def __otgw_worker(self):
        self._worker_running = True

        line_regex = re.compile(r'^.*[\r\n]+')

        buffer = ""
        while self._worker_running:
            buffer += self.__otgwClient.read()
            # Find all the lines in the read data
            while True:
                m = line_regex.match(buffer)
                if not m:
                    break
                line = m.group().rstrip('\r\n')
                # log.info("Line: {}".format(line))
                operation = self.__otgw.processLine(line)
                if operation:
                    try:
                        if isinstance(operation, OTGW.Message):
                            self.__on_otgw_message(message=operation)
                            self.__oled.on_otgw_message(msg=operation)
                        elif isinstance(operation, OTGW.Command):
                            if not operation.processed:
                                self.__otgwClient.write(operation.command)
                                operation.sent = True
                            else:
                                log.info("Processed command: {}".format(operation))
                    except Exception as e:
                        log.warning(str(e))

                # Strip the consumed line from the buffer
                buffer = buffer[m.end():]

        self._worker_thread = None

