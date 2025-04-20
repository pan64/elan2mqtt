import asyncio
from asyncio import Queue
from typing import Callable, Coroutine, Any

import aiomqtt
import logging
from config import Config

logger = logging.getLogger(__name__)

class PublishData:
    def __init__(self, topic: str, payload: str, message: str):
        """
        init publish data struct
        :param topic: topic
        :param payload:payload
        :param message:message
        """
        self.topic = topic
        self.payload = payload
        self.message = message

class MqttClient:

    username: str
    password: str
    url: str
    name: str
    client: aiomqtt.Client

    lock = asyncio.Lock()

    queue: Queue = Queue()

    def __init__(self, name: str):
        self.name = name

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

    def publish(self, topic: str, payload: str, message: str):
        """
        put publish message into queue
        :param topic: topic
        :param payload: payload
        :param message: message
        """
        self.queue.put_nowait(PublishData(topic, payload, message))

    async def do_publish(self):
        """ do the real publish, process the queue"""
        while True:
            if self.queue.empty():
                await asyncio.sleep(10)
                continue
            pdata: PublishData = self.queue.get_nowait()
            async with self.client as client:
                await client.publish(pdata.topic, bytearray(pdata.payload, 'utf-8'))
            logger.info("{}: topic '{}' is published '{}'".format(pdata.message, pdata.topic, pdata.payload))

    async def listen(self, topic: str, callback: Callable[[str, str], Coroutine[Any, Any, None]]):
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


