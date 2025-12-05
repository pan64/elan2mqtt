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
    config: Config

    lock = asyncio.Lock()

    def __init__(self, name: str):
        self.name = name
        self.queue: Queue = Queue()

    def setup(self, config: Config) -> None:
        """configure this mqtt client"""
        try:
            self.config = config
            self.username = config['options']['mqtt_user']
            self.password = config['options']['mqtt_pass']
            self.url = config['options']['MQTTserver']
            self.name = config['options']['mqtt_id']
        except KeyError as e:
            logger.error("Missing required MQTT configuration: {}".format(str(e)))
            raise ValueError("Invalid MQTT configuration") from e
        except Exception as e:
            logger.error("Error setting up MQTT client: {}".format(str(e)))
            raise

    def connect(self) -> None:
        """connect to broker"""
        try:
            if not hasattr(self, 'url') or not self.url:
                raise ValueError("MQTT URL not configured")
            self.client = aiomqtt.Client(hostname=self.url, username=self.username, password=self.password, logger=logger)
            logger.info("mqtt is connected to {}".format(self.url))
        except (ValueError, TypeError) as e:
            logger.error("MQTT connection configuration error: {}".format(str(e)))
            raise
        except Exception as e:
            logger.error("Failed to create MQTT client: {}".format(str(e)))
            raise

    def publish(self, topic: str, payload: str, message: str) -> None:
        """
        put publish message into queue
        :param topic: topic
        :param payload: payload
        :param message: message
        """
        if not topic:
            logger.error("Cannot publish to empty topic")
            return
        if payload is None:
            logger.warning("Publishing None payload to topic: {}".format(topic))
            payload = ""
        
        try:
            self.queue.put_nowait(PublishData(topic, str(payload), message))
        except asyncio.QueueFull:
            logger.warning("MQTT publish queue is full, dropping message for topic: {}".format(topic))
        except Exception as e:
            logger.error("Failed to queue message for topic '{}': {}".format(topic, str(e)))

    async def do_publish(self) -> None:
        """ do the real publish, process the queue"""
        while True:
            try:
                async with aiomqtt.Client(hostname=self.url, username=self.username, password=self.password, logger=logger) as client:
                    while True:
                        try:
                            pdata: PublishData = await self.queue.get()
                            await client.publish(pdata.topic, bytearray(pdata.payload, 'utf-8'))
                            logger.info("{}: topic '{}' is published '{}'".format(pdata.message, pdata.topic, pdata.payload))
                            self.queue.task_done()
                        except aiomqtt.MqttError as e:
                            logger.error("MQTT publish error for topic '{}': {}".format(pdata.topic if 'pdata' in locals() else 'unknown', str(e)), exc_info=True)
                            self.queue.task_done()
                        except UnicodeEncodeError as e:
                            logger.error("Encoding error for payload: {}".format(str(e)))
                            self.queue.task_done()
                        except asyncio.CancelledError:
                            logger.info("Publish task cancelled")
                            raise
            except (ConnectionError, OSError) as e:
                delay = self.config['internal']['constants']['MQTT_RECONNECT_DELAY']
                logger.error("MQTT connection error, retrying in {} seconds: {}".format(delay, str(e)))
                await asyncio.sleep(delay)
            except Exception as e:
                logger.error("Unexpected error in publish loop: {}".format(str(e)))
                await asyncio.sleep(self.config['internal']['constants']['ERROR_RETRY_DELAY'])

    async def listen(self, topic: str, callback: Callable[[str, str], Coroutine[Any, Any, None]]):
        """
        listens to the subscribed topics
        :param topic: topic wildcard to listen to
        :param callback: callback function to handle events
        """
        if not topic:
            raise ValueError("Topic cannot be empty")
        
        logger.info("listening on '{}'".format(topic))

        while True:
            try:
                async with aiomqtt.Client(hostname=self.url, username=self.username, password=self.password, logger=logger) as client:
                    await client.subscribe(topic)
                    logger.info("subscribed to topic: {}".format(topic))
                    async for message in client.messages:
                        try:
                            topic_parts = message.topic.value.split("/")
                            if len(topic_parts) < 2:
                                logger.warning("Invalid topic format: {}".format(message.topic.value))
                                continue
                            mac = topic_parts[1]
                            payload = message.payload.decode("utf-8")
                            await callback(mac, payload)
                        except UnicodeDecodeError as e:
                            logger.error("Failed to decode message payload: {}".format(str(e)))
                        except IndexError as e:
                            logger.error("Invalid topic structure '{}': {}".format(message.topic.value, str(e)))
                        except Exception as e:
                            logger.error("Error processing message from '{}': {}".format(message.topic.value, str(e)))
            except aiomqtt.MqttError as e:
                logger.error("MQTT connection error: {}".format(str(e)))
                await asyncio.sleep(self.config['internal']['constants']['MQTT_RECONNECT_DELAY'])
            except (ConnectionError, OSError) as e:
                logger.error("Network connection error: {}".format(str(e)))
                await asyncio.sleep(self.config['internal']['constants']['NETWORK_RECONNECT_DELAY'])
            except asyncio.CancelledError:
                logger.info("MQTT listener cancelled")
                raise
            except Exception as e:
                logger.error("Unexpected error in MQTT listener: {}".format(str(e)))
            await asyncio.sleep(self.config['internal']['constants']['ERROR_RETRY_DELAY'])
            logger.info("restarting mqtt listener")


