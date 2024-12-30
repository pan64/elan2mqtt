import argparse
import asyncio
import json
import logging
import sys
from typing import List
import time

import elan_client
import mqtt_client

import device
from device import Device

logger = logging.getLogger(__name__)

config_data: dict = {}
elan: elan_client.ElanClient = elan_client.ElanClient()
mqtt: mqtt_client.MqttClient = mqtt_client.MqttClient("main")

device.elan = elan
device.mqtt = mqtt

devices: List[Device] = []
device_hash: dict[str: Device] = {}


async def read_config() -> None:
    logger.info("loading config file")
    global config_data

    try:
        with open("config.json", "r", encoding="utf8") as json_file:
            config_data = json.load(json_file)
    except BaseException as be:
        logger.error("read config exception occurred")
        logger.error(be, exc_info=True)
        config_data = {}
        raise

def get_devices():
    global devices
    global elan
    global device_hash
    device_list: dict = elan.get('/api/devices')
    print(device_list)
    for d in device_list.values():
        dev = Device(d["url"])
        devices.append(dev)
        device_hash[dev.id] = dev
    mqtt_client.device_hash = device_hash

async def publish_all():
    last_publish = 0
    while True:
        needed = last_publish + config_data['options']['publish_interval'] - time.time()
        if needed > 0:
            logger.info("waiting {} secs for the next publish".format(needed))
            await asyncio.sleep(needed)
        for dev in devices:
            await dev.publish()
        last_publish = time.time()

async def discover_all():
    last_discover = 0
    while True:
        needed = last_discover + config_data['options']['discover_interval'] - time.time()
        if needed > 0:
            logger.info("waiting {} secs for the next discover".format(needed))
            await asyncio.sleep(needed)
        dev: Device
        for dev in devices:
            await dev.discover()
        last_discover = time.time()

async def elan_ws():
    last_socket = 0
    while True:
        needed = last_socket + config_data['options']['socket_interval'] - time.time()
        if needed > 0:
            logger.info("waiting {} secs for the next websocket".format(needed))
            await asyncio.sleep(needed)
        data = await elan.ws_json()
        try:
            await device_hash[data['device']].publish()
        except BaseException as be:
            logger.error("websocket error occurred")
            logger.error(data)
            logger.error(device_hash)
            logger.error(be, exc_info=True)
        last_socket = time.time()

async def process_event(mac: str, payload: str):
    if mac in device_hash:
        await device_hash[mac].process_command(payload)

def subscribe_all():
    asyncio.create_task(mqtt.listen("eLan/+/command", process_event))



async def main():
    global logger
    await read_config()
    elan.setup(config_data)
    mqtt.setup(config_data)
    mqtt.connect()
    get_devices()

    logger.info("{} devices have been found in eLan".format(len(devices)))

    asyncio.create_task(publish_all())
    if config_data['options']['disable_autodiscovery'] == False:
        asyncio.create_task(discover_all())
    asyncio.create_task(elan_ws())
    subscribe_all()

    while True:
        await asyncio.sleep(10)


def str2bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


if __name__ == '__main__':
    # parse arguments
    parser = argparse.ArgumentParser(description='Process some arguments.')
    parser.add_argument(
        '-log-level',
        metavar='log_level',
        nargs=1,
        dest='log_level',
        default='debug',
        help='Log level debug|info|warning|error|fatal')
    parser.add_argument(
        '-disable-autodiscovery',
        metavar='disable_autodiscovery',
        nargs='?',
        dest='disable_autodiscovery',
        default=False,
        type=str2bool,
        help='Disable autodiscovery True|False')

    args = parser.parse_args()

    formatter = "[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
    numeric_level = getattr(logging, args.log_level[0].upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = 30
    logging.basicConfig(level=0, format=formatter)

    # Loop forever
    # Any error will trigger new startup
    while True:
        try:
            asyncio.run(main())
        except elan_client.ElanException:
            logger.error("Cannot communicate with eLan")
        except:
            logger.exception(
                "MAIN WORKER: Something went wrong. But don't worry we will start over again.",
                exc_info=True)

        logger.error("But at first take some break. Sleeping for 10 s")
        sys.exit()
