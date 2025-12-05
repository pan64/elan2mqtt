import argparse
import asyncio
import logging

from typing import Dict, Any
import sys

import elan_client
import mqtt_client
from config import Config
from elan_logger import set_logger
from event_bus import event_bus, EventType
from device_manager import device_manager

from device import Device
from asyncio import TaskGroup

logger = logging.getLogger(__name__)

config_data: Config

elan: elan_client.ElanClient = elan_client.ElanClient()
mqtt: mqtt_client.MqttClient = mqtt_client.MqttClient("main")




def read_config() -> Config:
    """
    read the common config file into a dict
    """
    logger.info("loading config file")

    try:
        config = Config("config.json")
        return config
    except (FileNotFoundError, PermissionError) as e:
        logger.error("Config file access error: {}".format(str(e)))
        raise
    except (ValueError, TypeError) as e:
        logger.error("Config file format error: {}".format(str(e)))
        raise
    except Exception as e:
        logger.error("Unexpected error reading config: {}".format(str(e)))
        raise


def get_devices() -> None:
    """
    get list of available devices from elan
    """
    device_list: Dict[str, Any] = elan.get('/api/devices')
    device_manager.update_devices(device_list)
    logger.info("Loaded {} devices".format(len(device_manager.devices)))


async def handle_device_state_changed(device_id: str) -> None:
    """Handle device state change events"""
    if device_id in device_manager.device_hash:
        device_manager.device_hash[device_id].publish()

async def periodic_publish() -> None:
    """Periodic fallback publishing"""
    while True:
        await asyncio.sleep(config_data['options']['publish_interval'])
        for dev in device_manager.devices:
            await event_bus.publish(EventType.DEVICE_STATE_CHANGED, dev.id)



async def handle_device_discovered(device: Device) -> None:
    """Handle device discovery events"""
    await device.discover()

async def initial_discovery() -> None:
    """Initial device discovery"""
    for dev in device_manager.devices:
        await event_bus.publish(EventType.DEVICE_DISCOVERED, dev)

async def periodic_device_refresh() -> None:
    """Periodic device list refresh to handle device changes"""
    while True:
        await asyncio.sleep(config_data['options'].get('device_refresh_interval', 3600))
        try:
            get_devices()
            await initial_discovery()
        except Exception as e:
            logger.error("Device refresh failed: {}".format(str(e)))


async def elan_ws() -> None:
    """
    elan websocket listener loop
    """
    async def ws_handler(device_id: str) -> None:
        await event_bus.publish(EventType.DEVICE_STATE_CHANGED, device_id)

    while True:
        try:
            await elan.ws_listen(ws_handler)
        except (ConnectionError, OSError) as e:
            logger.error("WebSocket connection error: {}".format(str(e)))
            await asyncio.sleep(config_data['internal']['constants']['WEBSOCKET_ERROR_DELAY'])
        except Exception as e:
            logger.error("Unexpected WebSocket error: {}".format(str(e)))
            await asyncio.sleep(config_data['internal']['constants']['ERROR_RETRY_DELAY'])


async def handle_mqtt_command(data: Dict[str, str]) -> None:
    """Handle MQTT command events"""
    address = data.get('address')
    payload = data.get('payload')
    if address in device_manager.device_addr_hash:
        await device_manager.device_addr_hash[address].process_command(payload)
    else:
        logger.error("Device not found: {}".format(address))

async def process_event(address: str, payload: str) -> None:
    """MQTT event processor"""
    await event_bus.publish(EventType.MQTT_COMMAND_RECEIVED, {'address': address, 'payload': payload})



async def main() -> None:
    global logger
    asyncio.current_task().set_name("main")

    # Setup event handlers
    event_bus.subscribe(EventType.DEVICE_STATE_CHANGED, handle_device_state_changed)
    event_bus.subscribe(EventType.DEVICE_DISCOVERED, handle_device_discovered)
    event_bus.subscribe(EventType.MQTT_COMMAND_RECEIVED, handle_mqtt_command)

    # mqtt.connect()
    logger.info("{} devices have been found in eLan".format(len(device_manager.devices)))

    async with TaskGroup() as group:
        group.create_task(periodic_publish(), name="publish")
        group.create_task(periodic_device_refresh(), name="device_refresh")
        if not config_data['options']['disable_autodiscovery']:
            group.create_task(initial_discovery(), name="discover")
        group.create_task(elan_ws(), name="websocket")
        group.create_task(mqtt.do_publish(), name="mqtt")
        group.create_task(mqtt.listen("eLan/+/command", process_event), name="subscribe")

        logger.info("Event-driven system started")

    while True:
        await asyncio.sleep(config_data['internal']['constants']['MAIN_LOOP_INTERVAL'])


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
            read_config()
            elan.setup(config_data)
            mqtt.setup(config_data)
            Device.init(elan, mqtt)
            get_devices()

            asyncio.run(main())
        except KeyboardInterrupt:
            sys.exit(1)
        except (ConnectionError, OSError) as e:
            logger.error("Network connection error: {}".format(str(e)))
        except (ValueError, TypeError) as e:
            logger.error("Configuration or data error: {}".format(str(e)))
        except Exception as e:
            logger.exception("Unexpected error in main worker: {}".format(str(e)))

        logger.error("But at first take some break. Sleeping for {} s".format(config_data['internal']['constants']['MAIN_LOOP_INTERVAL']))
