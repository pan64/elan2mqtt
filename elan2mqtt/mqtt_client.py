import asyncio

import aiomqtt
import logging
logger = logging.getLogger(__name__)
from config import Config

class MqttClient:

    username: str
    password: str
    url: str
    name: str
    client: aiomqtt.Client

    lock = asyncio.Lock()

    def __init__(self, name: str):
        self.name = name
        pass

    def setup(self, config: Config):
        """configure this mqtt client"""
        self.username = config['options']['mqtt_user']
        self.password = config['options']['mqtt_pass']
        self.url = config['options']['MQTTserver']
        self.name = config['options']['mqtt_id']

    def connect(self):
        """connect to broker"""
        self.client = aiomqtt.Client(hostname=self.url, username=self.username, password=self.password, logger=logger)
        logger.info("mqtt is connected to {}".format(self.url))

    async def publish(self, topic: str, payload: str):
        """
        publish message
        :param topic: topic
        :param payload: payload
        """
        async with self.lock:
            async with self.client as client:
                await client.publish(topic, bytearray(payload, 'utf-8'))
            logger.info("topic '{}' is published '{}'".format(topic, payload))

    async def listen(self, topic: str, callback):
        """
        listens to the subscribed topics
        :param topic: topic wildcard to listen to
        :param callback: callback function to handle events
        """
#        async with self.lock:
        logger.info("listening on '{}'".format(topic))

        async with aiomqtt.Client(hostname=self.url, username=self.username, password=self.password, logger=logger) as client:
            await client.subscribe(topic)
            logger.info("listening: message arrived")
            async for message in client.messages:
                mac = message.topic.value.split("/")[1]
                await callback(mac, message.payload.decode("utf-8"))
        logger.info("listening on {} ended".format(topic))


