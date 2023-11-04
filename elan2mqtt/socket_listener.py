# -*- coding: utf-8 -*-

##########################################################################
#
# This is eLAN to MQTT gateway
#
# It operates in single monolithic loop which periodically:
# - checks for websocket messages and processes them
#
# The JSON messages between the MQTT and eLAN are passed without processing
#  - status_topic: eLan/ADDR_OF_DEVICE/status
#  - control_topic: eLan/ADDR_OF_DEVICE/command
#
#
##########################################################################

import argparse
import asyncio

import mqtt_client
import elan_client

import json

import logging
import time

logger = logging.getLogger(__name__)

pending_message = []


class ClientException(BaseException):
    pass


async def main():
    # placeholder for devices data
    d = {}
    u = {}

    async def publish_status(mac_d):
        """Publish message to status topic. Topic syntax is: elan / mac / status """
        if mac_d in d:
            logger.info("Getting and publishing status for " + d[mac_d]['url'])
            resp = await elan_cli.get(d[mac_d]['url'] + '/state')
            mqtt_cli.publish(d[mac_d]['status_topic'],
                             bytearray(json.dumps(resp), 'utf-8'))
            logger.info("Status published for " + d[mac_d]['url'] + " " + str(resp))

    mqtt_cli: mqtt_client.MqttClient = mqtt_client.MqttClient("socket_listener")
    logger.info("Connecting to MQTT broker")

    elan_cli: elan_client.ElanClient = elan_client.ElanClient()
    elan_cli.setup()
    await elan_cli.login()

    # Let's give MQTT some time to connect
    time.sleep(5)

    if not mqtt_cli.is_connected:
        raise Exception('MQTT not connected!')

    # Get list of devices
    # If we are not authenticated it will raise exception due to json
    logger.info("Getting eLan device list")
    device_list: dict = await elan_cli.get('/api/devices')

    logger.info("Devices defined in eLan:\n" + str(device_list))

    mac = None

    for device in device_list:
        info = await elan_cli.get(device_list[device]['url'])
        device_list[device]['info'] = info

        if "address" in info['device info']:
            mac = str(info['device info']['address'])
        else:
            mac = str(info['id'])
            logger.error("There is no MAC for device " + str(device_list[device]))
            device_list[device]['info']['device info']['address'] = mac

        u[device] = mac

        logger.info("Setting up " + device_list[device]['url'])
        # print("Setting up ", device_list[device]['url'], device_list[device])

        d[mac] = {
            'info': info,
            'url': device_list[device]['url'],
            'status_topic': ('eLan/' + mac + '/status'),
            'control_topic': ('eLan/' + mac + '/command')
        }

        #
        # topic syntax is: elan / mac / command | status
        #

        # We are not subscribed to any command topic

        # publish status over mqtt
        # print("Publishing status to topic " + d[mac]['status_topic'])
        await publish_status(mac)

    logger.info("Connecting to websocket to get updates")
    websocket = await elan_cli.ws_connect()
    logger.info("Socket connected")

    # interval between mandatory messages to keep connections open (and to renew session) in s (eLan session expires in 0.5 h)
    keep_alive_interval = 1 * 60
    last_keep_alive = time.time()

    try:
        while True:  # Main loop
            # process status update announcement from eLan
            try:
                # every once so often do login
                if (time.time() - last_keep_alive) > keep_alive_interval:
                    last_keep_alive = time.time()
                    # await login(args.elan_user[0], str(args.elan_password[0]).encode('cp1250'))
                    if mac is not None:
                        logger.info("Keep alive - status for MAC " + mac)
                        await publish_status(mac)
                # Waiting for WebSocket eLan message
                echo = await websocket.receive_json()
                if echo is None:
                    time.sleep(.25)
                    # print("Empty message?")
                else:
                    # print(echo)
                    dev_id = echo["device"]
                    logger.info("Processing state change for " + u[dev_id])
                    await publish_status(u[dev_id])
            except:
                # It is perfectly normal to reach here - e.g. timeout
                logger.exception("Exception", exc_info=True)
                time.sleep(.1)
                raise ClientException("internal error")
            time.sleep(.1)

        # logger.error("Should not ever reach here")
        # await c.disconnect()
    except ClientException as ce:
        logger.error("SOCKET LISTENER: Client exception: %s" % ce)
        try:
            await mqtt_cli.disconnect()
        except:
            pass
        time.sleep(5)


if __name__ == '__main__':
    # parse arguments
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument(
        '-log-level',
        metavar='log_level',
        nargs=1,
        dest='log_level',
        default='warning',
        help='Log level debug|info|warning|error|fatal')

    args = parser.parse_args()

    formatter = "[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
    numeric_level = getattr(logging, args.log_level[0].upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = 30
    logging.basicConfig(level=numeric_level, format=formatter)

    # Loop forever
    # Any error will trigger new startup
    while True:
        try:
            asyncio.get_event_loop().run_until_complete(main())
        except:
            logger.exception(
                "SOCKET LISTENER: Something went wrong. But don't worry we will start over again."
            )
            logger.error("But at first take some break. Sleeping for 5 s")
            time.sleep(5)
