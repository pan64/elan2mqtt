import json
import logging
from typing import Any

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class MqttClient:
    connections = {}

    def __init__(self, name: str):
        self.my_name = "eLan2MQTT_main_worker_{0}".format(name)
        if self.my_name in self.connections:
            return
        broker = MqttClientBase(self.my_name)
        broker.setup()

    def connect(self) -> None:
        if self.is_connected():
            return
        broker = self.connections[self.my_name]
        broker.connect(1883, 120)
        broker.loop_start()

    def disconnect(self):
        if not self.is_connected():
            return
        self.connections[self.my_name].disconnect()

    def is_connected(self) -> bool:
        if self.my_name not in self.connections:
            return False
        return self.connections[self.my_name].is_connected()

    def publish(self, *args, **kwargs):
        if not self.is_connected():
            self.connect()
        return self.connections[self.my_name].publish(*args, **kwargs)

    def subscribe(self, *args, **kwargs):
        if not self.is_connected():
            self.connect()
        return self.connections[self.my_name].subscribe(*args, **kwargs)

    def has_message(self, *args, **kwargs):
        if not self.is_connected():
            self.connect()
        return self.connections[self.my_name].has_message(*args, **kwargs)

    def pop_message(self, *args, **kwargs):
        if not self.is_connected():
            self.connect()
        return self.connections[self.my_name].pop_message(*args, **kwargs)


class MqttClientBase(mqtt.Client):
    pending_message: list[Any] = []

    def __init__(self, name: str):
        super().__init__("eLan2MQTT_main_worker_{0}".format(name))
        self.mqtt_broker = None

    def on_connect_func(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT broker")
        else:
            logger.error("Bad connection Returned code = " + str(rc))

    def on_disconnect_func(self, client, userdata, rc):
        logger.info("MQTT broker disconnected. Reason: " + str(rc))

    def on_message_func(self, client, userdata, message):
        logger.info("MQTT broker message. " + str(message.topic))
        self.pending_message.append(message)

    def read_config(self) -> str:
        logger.info("loading config file")
        with open("config.json", "r") as json_file:
            data = json.load(json_file)
        result = data["options"]["MQTTserver"]
        logger.info("mqtt data: {}".format(result))
        return result

    def setup(self) -> None:
        mqtt_broker = self.read_config()
        i = mqtt_broker.find('mqtt://')
        if i < 0:
            raise Exception('MQTT URL not provided!')

        # Strip mqtt header from URL
        mqtt_broker = mqtt_broker[7:]

        i = mqtt_broker.find('@')
        mqtt_username = ""
        mqtt_password = ""

        # parse MQTT URL
        if i > 0:
            # We have credentials
            mqtt_username = mqtt_broker[0:i]
            mqtt_broker = mqtt_broker[i + 1:]
            i = mqtt_username.find(':')
            if i > 0:
                # We have password
                mqtt_password = mqtt_username[i + 1:]
                mqtt_username = mqtt_username[0:i]

        self.username_pw_set(username=mqtt_username, password=mqtt_password)
        # bind call back functions
        self.on_connect = self.on_connect_func
        self.on_disconnect = self.on_disconnect_func
        self.on_message = self.on_message_func
        self.mqtt_broker = mqtt_broker

    def has_message(self) -> bool:
        res = len(self.pending_message) > 0
        if res:
            logger.debug("MQTT has {} pending message(s)".format(len(self.pending_message)))
        return res

    def pop_message(self):
        logger.debug("pop message")
        return self.pending_message.pop(0)
