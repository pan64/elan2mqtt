import asyncio
import logging
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Queue as MPQueue, Manager

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


async def get_devices() -> None:
    """
    get list of available devices from elan
    """
    try:
        device_list: Dict[str, Any] = await elan.get('/api/devices')
        await device_manager.update_devices(device_list)
        logger.info("Loaded {} devices".format(len(device_manager.devices)))
    except (ConnectionError, OSError) as e:
        logger.error("Network error loading devices: {}".format(str(e)))
        raise
    except (KeyError, TypeError, ValueError) as e:
        logger.error("Invalid device data format: {}".format(str(e)))
        raise
    except Exception as e:
        logger.error("Unexpected error loading devices: {}".format(str(e)))
        raise


async def handle_device_state_changed(device_id: str) -> None:
    """Handle device state change events"""
    try:
        if device_id in device_manager.device_hash:
            device_manager.device_hash[device_id].publish()
    except Exception as e:
        logger.error("Error handling device state change for {}: {}".format(device_id, str(e)))


async def periodic_publish() -> None:
    """Periodic fallback publishing"""
    while True:
        try:
            await asyncio.sleep(config_data['options']['publish_interval'])
            for dev in device_manager.devices:
                await event_bus.publish(EventType.DEVICE_STATE_CHANGED, dev.id)
        except Exception as e:
            logger.error("Error in periodic publish: {}".format(str(e)))


async def handle_device_discovered(device: Device) -> None:
    """Handle device discovery events"""
    try:
        await device.discover()
    except Exception as e:
        logger.error("Error discovering device {}: {}".format(device.id if hasattr(device, 'id') else 'unknown', str(e)))


async def initial_discovery() -> None:
    """Initial device discovery"""
    try:
        for dev in device_manager.devices:
            await event_bus.publish(EventType.DEVICE_DISCOVERED, dev)
    except Exception as e:
        logger.error("Error in initial discovery: {}".format(str(e)))


async def periodic_device_refresh() -> None:
    """Periodic device list refresh to handle device changes"""
    while True:
        await asyncio.sleep(config_data['options'].get('device_refresh_interval', 3600))
        try:
            await get_devices()
            await initial_discovery()
        except Exception as e:
            logger.error("Device refresh failed: {}".format(str(e)))


def elan_ws_sync(config_dict: Dict[str, Any], device_queue: MPQueue, cookie_dict: Dict) -> None:
    """
    Synchronous elan websocket listener loop for ProcessPoolExecutor
    """
    import time  # noqa: E402
    import json  # noqa: E402
    from urllib.parse import urlparse, urlunparse  # noqa: E402
    from websockets.sync.client import connect as ws_connect_sync  # noqa: E402
    import logging as process_logging  # noqa: E402,W0404

    # Setup logging in process
    process_logger = process_logging.getLogger(__name__)

    elan_url = config_dict["options"]["eLanURL"]

    while True:
        try:
            cookie = cookie_dict.get('cookie')
            if not cookie:
                process_logger.error("No authentication cookie available")
                time.sleep(config_dict['internal']['constants']['WEBSOCKET_ERROR_DELAY'])
                continue

            headers = {'Cookie': "AuthAPI={}".format(cookie)}
            parsed = urlparse(elan_url)
            ws_scheme = "wss" if parsed.scheme == "https" else "ws"
            ws_host = urlunparse((ws_scheme, parsed.netloc, '/api/ws', '', '', ''))

            process_logger.debug("Connecting to websocket at {}".format(ws_host))
            ping_timeout = config_dict['internal']['constants']['WEBSOCKET_PING_TIMEOUT']

            with ws_connect_sync(ws_host, additional_headers=headers, ping_timeout=ping_timeout, open_timeout=10) as ws:
                process_logger.info("WebSocket connected")
                while True:
                    try:
                        message = ws.recv(timeout=config_dict['internal']['constants']['WEBSOCKET_RECV_TIMEOUT'])
                        data = json.loads(message)
                        device_id = data.get('device')
                        if device_id:
                            device_queue.put(device_id)
                            process_logger.debug("Received device update: {}".format(device_id))
                    except TimeoutError:
                        continue
                    except KeyError:
                        continue

        except Exception as e:
            process_logger.error("WebSocket error: {}".format(str(e)))
            # Invalidate cookie on connection error
            cookie_dict['cookie'] = None
            time.sleep(config_dict['internal']['constants']['WEBSOCKET_ERROR_DELAY'])


async def cookie_refresh_monitor(cookie_dict: Dict) -> None:
    """Monitor for cookie refresh requests from the websocket process"""
    while True:
        try:
            await asyncio.sleep(0.5)
            if cookie_dict.get('cookie') is None and elan.cookie is None:
                logger.info("Cookie refresh requested by websocket process")
                try:
                    await elan.connect(force=True)
                except Exception as e:
                    logger.error("Cookie refresh failed: {}".format(str(e)))
        except Exception as e:
            logger.error("Error in cookie refresh monitor: {}".format(str(e)))
            await asyncio.sleep(1)


async def elan_ws_monitor(device_queue: MPQueue) -> None:
    """Monitor the device queue from the sync websocket process"""
    while True:
        try:
            # Check queue in non-blocking way
            await asyncio.sleep(0.1)
            while not device_queue.empty():
                device_id = device_queue.get_nowait()
                await event_bus.publish(EventType.DEVICE_STATE_CHANGED, device_id)
        except Exception as e:
            logger.error("Error monitoring device queue: {}".format(str(e)))
            await asyncio.sleep(1)


async def handle_mqtt_command(data: Dict[str, str]) -> None:
    """Handle MQTT command events"""
    try:
        address = data.get('address')
        payload = data.get('payload')
        if address in device_manager.device_addr_hash:
            await device_manager.device_addr_hash[address].process_command(payload)
        else:
            logger.error("Device not found: {}".format(address))
    except (KeyError, TypeError) as e:
        logger.error("Invalid MQTT command data: {}".format(str(e)))
    except Exception as e:
        logger.error("Error handling MQTT command: {}".format(str(e)))


async def process_event(address: str, payload: str) -> None:
    """MQTT event processor"""
    try:
        await event_bus.publish(EventType.MQTT_COMMAND_RECEIVED, {'address': address, 'payload': payload})
    except Exception as e:
        logger.error("Error processing MQTT event: {}".format(str(e)))


async def main() -> None:
    asyncio.current_task().set_name("main")

    # Setup event handlers
    event_bus.subscribe(EventType.DEVICE_STATE_CHANGED, handle_device_state_changed)
    event_bus.subscribe(EventType.DEVICE_DISCOVERED, handle_device_discovered)
    event_bus.subscribe(EventType.MQTT_COMMAND_RECEIVED, handle_mqtt_command)

    # mqtt.connect()
    logger.info("{} devices have been found in eLan".format(len(device_manager.devices)))

    # Create ProcessPoolExecutor for websocket listener
    executor = ProcessPoolExecutor(max_workers=1)

    # Create shared manager for inter-process communication
    manager = Manager()
    device_queue = manager.Queue()
    cookie_dict = manager.dict()

    # Set the shared cookie dict on elan client
    elan.cookie_dict = cookie_dict

    # Submit websocket listener to process pool
    executor.submit(elan_ws_sync, config_data.data, device_queue, cookie_dict)

    try:
        async with TaskGroup() as group:
            group.create_task(cookie_refresh_monitor(cookie_dict), name="cookie_refresh")
            group.create_task(periodic_publish(), name="publish")
            group.create_task(periodic_device_refresh(), name="device_refresh")
            if not config_data['options']['disable_autodiscovery']:
                group.create_task(initial_discovery(), name="discover")
            group.create_task(elan_ws_monitor(device_queue), name="websocket_monitor")
            group.create_task(mqtt.do_publish(), name="mqtt")
            group.create_task(mqtt.listen("eLan/+/command", process_event), name="subscribe")

            logger.info("Event-driven system started with process pool executor")
    finally:
        logger.info("Shutting down process pool executor")
        executor.shutdown(wait=True)
        manager.shutdown()

    while True:
        await asyncio.sleep(config_data['internal']['constants']['MAIN_LOOP_INTERVAL'])


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
            asyncio.run(get_devices())

            asyncio.run(main())
        except KeyboardInterrupt:
            sys.exit(1)
        except (ConnectionError, OSError) as e:
            logger.error("Network connection error: {}".format(str(e)))
            asyncio.run(elan.cleanup())
        except (ValueError, TypeError) as e:
            logger.error("Configuration or data error: {}".format(str(e)))
            asyncio.run(elan.cleanup())
        except Exception as e:
            logger.exception("Unexpected error in main worker: {}".format(str(e)))
            asyncio.run(elan.cleanup())

        logger.error("But at first take some break. Sleeping for {} s".format(config_data['internal']['constants']['MAIN_LOOP_INTERVAL']))
