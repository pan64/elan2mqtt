import asyncio
import aiomqtt
import logging
logger = logging.getLogger(__name__)

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

    def setup(self, config: dict):
        self.username = config['options']['mqtt_user']
        self.password = config['options']['mqtt_pass']
        self.url = config['options']['MQTTserver']
        self.name = config['options']['mqtt_id']

    def connect(self):
        self.client = aiomqtt.Client(hostname=self.url, username=self.username, password=self.password, logger=logger)
        logger.info("mqtt is connected to {}".format(self.url))

    async def publish(self, topic: str, payload: str):
        async with self.lock:
            async with self.client as client:
                await self.client.publish(topic, payload)
            logger.info("topic {} is published".format(topic))

    async def listen(self, topic: str, callback):
#        async with self.lock:
            logger.info("listening on {}".format(topic))

            async with aiomqtt.Client(hostname=self.url, username=self.username, password=self.password, logger=logger) as client:
                await client.subscribe(topic)
                async for message in client.messages:
                    mac = message.topic.value.split("/")[1]
                    await callback(mac, message.payload)
                    print(message.payload)
            logger.info("listening on {} ended".format(topic))


