import argparse
import asyncio
import logging
from typing import List
import time

import elan_client
import mqtt_client
from config import Config
from elan_logger import set_logger

from device import Device
from asyncio import TaskGroup

logger = logging.getLogger(__name__)

config_data: Config

elan: elan_client.ElanClient = elan_client.ElanClient()
mqtt: mqtt_client.MqttClient = mqtt_client.MqttClient("main")

devices: List[Device] = []
device_hash: dict[str, Device] = {}
device_addr_hash: dict[str, Device] = {}


def read_config() -> Config:
    """
    read the common config file into a dict
    """
    logger.info("loading config file")

    try:
        config = Config("config.json")
        return config
    except BaseException as be:
        logger.error("read config exception occurred")
        logger.error(be, exc_info=True)
        raise


def get_devices():
    """
    get list of available devices from elan
    """
    global devices
    global elan
    global device_hash
    device_list: dict = elan.get('/api/devices')
    for d in device_list.values():
        dev = Device.create(d["url"])
        devices.append(dev)
        device_hash[dev.id] = dev
        device_addr_hash[str(dev.data['device info']['address'])] = dev
    mqtt_client.device_hash = device_hash
    logger.warning(device_list)
    logger.warning(device_hash.keys())
    logger.warning(device_addr_hash.keys())


async def publish_all():
    """
    send general publish state messages to mqtt in loop
    """
    last_publish = 0
    while True:
        needed = last_publish + config_data['options']['publish_interval'] - time.time()
        if needed > 0:
            logger.info("waiting {} secs for the next publish".format(round(needed)))
            await asyncio.sleep(needed)
        for dev in devices:
            dev.publish()
        last_publish = time.time()



async def discover_all():
    """
    send discover messages to mqtt in loop
    """
    last_discover = 0
    while True:
        needed = last_discover + config_data['options']['discover_interval'] - time.time()
        if needed > 0:
            logger.info("waiting {} secs for the next discover".format(round(needed)))
            await asyncio.sleep(needed)
        dev: Device
        for dev in devices:
            await dev.discover()
        last_discover = time.time()


async def elan_ws():
    """
    elan websocket listener loop
    """
    global device_hash

    last_socket = 0
    while True:
        retry: bool = False
        data: dict = {}
        needed = last_socket + config_data['options']['socket_interval'] - time.time()
        if needed > 0:
            logger.info("waiting {} secs for the next websocket".format(round(needed)))
            await asyncio.sleep(needed)
        try:
            data = await elan.ws_json()
        except BaseException as be:
            logger.error("websocket error occurred")
            logger.error(be, exc_info=True)
            retry = True
        if not data:
            retry = True
        elif not data['device'] in device_hash:
            retry = True
        try:
            if not retry:
                device_hash[data['device']].publish()
        except BaseException as be:
            logger.error("websocket publish error occurred {} {}".format(data, device_hash[data['device']].data))
            logger.error(be, exc_info=True)
            retry = True

        if retry:
            await asyncio.sleep(1)

        last_socket = time.time()


async def process_event(address: str, payload: str):
    """
    handle event on the given device
    :param address: address of the device
    :param payload: command to process
    """
    if address in device_addr_hash:
        await device_addr_hash[address].process_command(payload)
    else:
        logger.error("process_event error occurred")
        logger.error(address)
        logger.error(payload)
        logger.error(device_hash)


async def main():
    global logger
    asyncio.current_task().set_name("main")

    read_config()
    elan.setup(config_data)
    mqtt.setup(config_data)
    Device.init(elan, mqtt)
    mqtt.connect()
    get_devices()

    logger.info("{} devices have been found in eLan".format(len(devices)))

    async with TaskGroup() as group:
        group.create_task(publish_all(), name="publish")
        if not config_data['options']['disable_autodiscovery']:
            group.create_task(discover_all(), name="discover")
        group.create_task(elan_ws(), name="websocket")
        group.create_task(mqtt.do_publish(), name="mqtt")
        group.create_task(mqtt.listen("eLan/+/command", process_event), name="subscribe")

        logger.info("all tasks have been created {}".format(asyncio.all_tasks()))

    while True:
        logger.info("running tasks: {}".format(len(asyncio.all_tasks())))
        await asyncio.sleep(10)


def str2bool(v) -> bool:
    """convert string to bool"""
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
    config_data = read_config()
    set_logger(config_data)

    # Loop forever
    # Any error will trigger new startup
    while True:
        try:
            asyncio.run(main())
        except:
            logger.exception(
                "MAIN WORKER: Something went wrong. But don't worry we will start over again.",
                exc_info=True)

        logger.error("But at first take some break. Sleeping for 10 s")
