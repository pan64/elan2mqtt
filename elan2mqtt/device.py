from elan_client import ElanClient
from mqtt_client import MqttClient

import logging
import json
import asyncio


elan: ElanClient
mqtt: MqttClient
logger: logging.Logger = logging.getLogger(__name__)


class Device:
    """one eLan device"""
    data: dict = {}
    def __init__(self, url: str):
        data: dict = {}

        try:
            info = elan.get(url)

            if "address" in info['device info']:
                mac = str(info['device info']['address'])
            else:
                mac = str(info['id'])
                logger.error("There is no MAC for device " + url)
                info['device info']['address'] = mac

            logger.info("Setting up " + url)
            # print("Setting up ", device_list[device]['url'], device_list[device])

            info['mac'] = mac
            info['url'] = url
            info["status_topic"] = 'eLan/' + mac + '/status'
            info["control_topic"] = 'eLan/' + mac + '/command'
            
            if "product type" in info['device info']:
                # placeholder for device type versus product type check
                pass
            else:
                info['product type'] = '---'

        except BaseException as be:
            logger.error("read elan device data exception occurred")
            logger.error(be, exc_info=True)
            raise
        self.data = info
        
        self.set_discovery()

    def __getattr__(self, item: str):
        if item in self.data:
            return self.data[item]

    def set_discovery(self):
        ddd={}
        if ('light' in self.data['device info']['type']) or (
                'lamp' in self.data['device info']['type']) or (
                self.data['device info']['product type'] == 'RFDA-11B'):
            logger.info(self.data['device info'])

            if 'on' in self.data['primary actions']:
                logger.info("Primary action of light is ON")
                discovery = {
                    'schema': 'basic',
                    'name': self.data['device info']['label'],
                    'unique_id': ('eLan-' + self.data['mac']),
                    'device': {
                        'name': self.data['device info']['label'],
                        'identifiers': ('eLan-light-' + self.data['mac']),
                        'connections': [["self.data['mac']", self.data['mac']]],
                        'mf': 'Elko EP',
                        'mdl': self.data['device info']['product type']
                    },
                    'command_topic': self.data['control_topic'],
                    'state_topic': self.data['status_topic'],
                    'json_attributes_topic': self.data['status_topic'],
                    'payload_off': '{"on":false}',
                    'payload_on': '{"on":true}',
                    'state_value_template':
                        '{%- if value_json.on -%}{"on":true}{%- else -%}{"on":false}{%- endif -%}'
                }
                ddd['homeassistant/light/' + self.data['mac'] + '/config'] = bytearray(json.dumps(discovery), 'utf-8')
                self.data['discovery'] = ddd
                return

            if ('brightness' in self.data['primary actions']) or (
                    self.data['device info']['product type'] == 'RFDA-11B'):
                logger.info("Primary action of light is BRIGHTNESS")
                discovery = {
                    'schema': 'template',
                    'name': self.data['device info']['label'],
                    'unique_id': ('eLan-' + self.data['mac']),
                    'device': {
                        'name': self.data['device info']['label'],
                        'identifiers': ('eLan-dimmer-' + self.data['mac']),
                        'connections': [["self.data['mac']", self.data['mac']]],
                        'mf': 'Elko EP',
                        'mdl': self.data['device info']['product type']
                    },
                    'state_topic': self.data['status_topic'],
                    # 'json_attributes_topic': self.data['status_topic'],
                    'command_topic': self.data['control_topic'],
                    'command_on_template':
                        '{%- if brightness is defined -%} {"brightness": {{ (brightness * '
                        + str(self.data['actions info']['brightness']
                              ['max']) +
                        ' / 255 ) | int }} } {%- else -%} {"brightness": 100 } {%- endif -%}',
                    'command_off_template': '{"brightness": 0 }',
                    'state_template':
                        '{%- if value_json.brightness > 0 -%}on{%- else -%}off{%- endif -%}',
                    'brightness_template':
                        '{{ (value_json.brightness * 255 / ' + str(
                            self.data['actions info']['brightness']
                            ['max']) + ') | int }}'
                }
                ddd['homeassistant/light/' + self.data['mac'] + '/config'] = bytearray(json.dumps(discovery), 'utf-8')
                self.data['discovery'] = ddd
                return


        #
        # Switches
        # RFSA-6xM units and "appliance" class of eLan
        # Note: handled as ELSE of light entities to avoid lights on RFSA-6xM units
        elif ('appliance' in self.data['device info']['type']) or (
                self.data['device info']['product type'] == 'RFSA-61M') or (
                self.data['device info']['product type'] == 'RFSA-66M') or (
                self.data['device info']['product type'] == 'RFSA-11B') or (
                self.data['device info']['product type'] == 'RFUS-61') or (
                self.data['device info']['product type'] == 'RFSA-62B'):
            logger.info(self.data['device info'])
            # "on" primary action is required for switches
            if 'on' in self.data['primary actions']:
                logger.info("Primary action of device is ON")
                discovery = {
                    'schema': 'basic',
                    'name': self.data['device info']['label'],
                    'unique_id': ('eLan-' + self.data['mac']),
                    'device': {
                        'name': self.data['device info']['label'],
                        'identifiers': ('eLan-switch-' + self.data['mac']),
                        'connections': [["self.data['mac']", self.data['mac']]],
                        'mf': 'Elko EP',
                        'mdl': self.data['device info']['product type']
                    },
                    'command_topic': self.data['control_topic'],
                    'state_topic': self.data['status_topic'],
                    'json_attributes_topic': self.data['status_topic'],
                    'payload_off': '{"on":false}',
                    'payload_on': '{"on":true}',
                    'state_off': 'off',
                    'state_on': 'on',
                    'value_template':
                        '{%- if value_json.on -%}on{%- else -%}off{%- endif -%}'
                }
                ddd['homeassistant/switch/' + self.data['mac'] + '/config'] = bytearray(json.dumps(discovery), 'utf-8')
                self.data['discovery'] = ddd
                return

        #
        # Thermostats
        #
        # User should set type to heating. But sometimes...
        # That is why we will always treat RFSTI-11G a temperature sensor/thermostat
        #
        if (self.data['device info']['type'] == 'heating') or (
                self.data['device info']['product type'] == 'RFSTI-11G'):
            logger.info(self.data['device info'])

            discovery = {
                'name': self.data['device info']['label'] + '-IN',
                'unique_id': ('eLan-' + self.data['mac'] + '-IN'),
                'device': {
                    'name': self.data['device info']['label'],
                    'identifiers': ('eLan-thermostat-' + self.data['mac']),
                    'connections': [["self.data['mac']", self.data['mac']]],
                    'mf': 'Elko EP',
                    'mdl': self.data['device info']['product type']
                },
                'device_class': 'temperature',
                'state_topic': self.data['status_topic'],
                'json_attributes_topic': self.data['status_topic'],
                'value_template': '{{ value_json["temperature IN"] }}',
                'unit_of_measurement': '°C'
            }
            ddd['homeassistant/sensor/' + self.data['mac'] + '/IN/config'] = bytearray(json.dumps(discovery), 'utf-8')

            discovery = {
                'name': self.data['device info']['label'] + '-OUT',
                'unique_id': ('eLan-' + self.data['mac'] + '-OUT'),
                'device': {
                    'name': self.data['device info']['label'],
                    'identifiers': ('eLan-thermostat-' + self.data['mac']),
                    'connections': [["self.data['mac']", self.data['mac']]],
                    'mf': 'Elko EP',
                    'mdl': self.data['device info']['product type']
                },
                'state_topic': self.data['status_topic'],
                'json_attributes_topic': self.data['status_topic'],
                'device_class': 'temperature',
                'value_template': '{{ value_json["temperature OUT"] }}',
                'unit_of_measurement': '°C'
            }
            ddd['homeassistant/sensor/' + self.data['mac'] + '/OUT/config'] = bytearray(json.dumps(discovery), 'utf-8')
            self.data['discovery'] = ddd
            return
        #
        # Thermometers
        #
        # User should set type to thermometer. But sometimes...
        #

        if (self.data['device info']['type'] == 'thermometer') or (
                self.data['device info']['product type'] == 'RFTI-10B'):
            logger.info(self.data['device info'])

            discovery = {
                'name': self.data['device info']['label'] + '-IN',
                'unique_id': ('eLan-' + self.data['mac'] + '-IN'),
                'device': {
                    'name': self.data['device info']['label'],
                    'identifiers': ('eLan-thermometer-' + self.data['mac']),
                    'connections': [["self.data['mac']", self.data['mac']]],
                    'mf': 'Elko EP',
                    'mdl': self.data['device info']['product type']
                },
                'device_class': 'temperature',
                'state_topic': self.data['status_topic'],
                'json_attributes_topic': self.data['status_topic'],
                'value_template': '{{ value_json["temperature IN"] }}',
                'unit_of_measurement': '°C'
            }
            ddd['homeassistant/sensor/' + self.data['mac'] + '/IN/config'] = bytearray(json.dumps(discovery), 'utf-8')

            discovery = {
                'name': self.data['device info']['label'] + '-OUT',
                'unique_id': ('eLan-' + self.data['mac'] + '-OUT'),
                'device': {
                    'name': self.data['device info']['label'],
                    'identifiers': ('eLan-thermometer-' + self.data['mac']),
                    'connections': [["self.data['mac']", self.data['mac']]],
                    'mf': 'Elko EP',
                    'mdl': self.data['device info']['product type']
                },
                'state_topic': self.data['status_topic'],
                'json_attributes_topic': self.data['status_topic'],
                'device_class': 'temperature',
                'value_template': '{{ value_json["temperature OUT"] }}',
                'unit_of_measurement': '°C'
            }
            ddd['homeassistant/sensor/' + self.data['mac'] + '/OUT/config'] = bytearray(json.dumps(discovery), 'utf-8')
            self.data['discovery'] = ddd
            return
        #
        # Detectors
        #
        # RFWD-100 status messages
        # {alarm: true, detect: false, tamper: “closed”, automat: false, battery: true, disarm: false}
        # {alarm: true, detect: true, tamper: “closed”, automat: false, battery: true, disarm: false}
        # RFSF-1B status message
        # {"alarm": false,	"detect": false, "automat": true, "battery": true, "disarm": false }

        if ('detector' in self.data['device info']['type']) or (
                'RFWD-' in self.data['device info']['product type']) or (
                'RFSD-' in self.data['device info']['product type']) or (
                'RFMD-' in self.data['device info']['product type']) or (
                'RFSF-' in self.data['device info']['product type']):
            logger.info(self.data['device info'])

            icon = ''

            # A wild guess of icon
            if ('window' in self.data['device info']['type']) or (
                    'RFWD-' in self.data['device info']['product type']):
                icon = 'mdi:window-open'
                if 'door' in str(self.data['device info']['label']).lower():
                    icon = 'mdi:door-open'

            if ('smoke' in self.data['device info']['type']) or (
                    'RFSD-' in self.data['device info']['product type']):
                icon = 'mdi:smoke-detector'

            if ('motion' in self.data['device info']['type']) or (
                    'RFMD-' in self.data['device info']['product type']):
                icon = 'mdi:motion-sensor'

            if ('flood' in self.data['device info']['type']) or (
                    'RFSF-' in self.data['device info']['product type']):
                icon = 'mdi:waves'

            # Silently expect that all detectors provide "detect" action
            discovery = {
                'name': self.data['device info']['label'],
                'unique_id': ('eLan-' + self.data['mac']),
                'device': {
                    'name': self.data['device info']['label'],
                    'identifiers': ('eLan-detector-' + self.data['mac']),
                    'connections': [["self.data['mac']", self.data['mac']]],
                    'mf': 'Elko EP',
                    'mdl': self.data['device info']['product type']
                },
                'state_topic': self.data['status_topic'],
                'json_attributes_topic': self.data['status_topic'],
                #                    'device_class': 'heat',
                'value_template':
                    '{%- if value_json.detect -%}on{%- else -%}off{%- endif -%}'
                #                    'command_topic': self.data['control_topic']
            }

            if icon != '':
                discovery['icon'] = icon

            ddd['homeassistant/sensor/' + self.data['mac'] + '/config'] = bytearray(json.dumps(discovery), 'utf-8')


            # Silently expect that all detectors provide "battery" status
            # Battery
            discovery = {
                'name': self.data['device info']['label'] + 'battery',
                'unique_id': ('eLan-' + self.data['mac'] + '-battery'),
                'device': {
                    'name': self.data['device info']['label'],
                    'identifiers': ('eLan-detector-' + self.data['mac']),
                    'connections': [["self.data['mac']", self.data['mac']]],
                    'mf': 'Elko EP',
                    'mdl': self.data['device info']['product type']
                },
                'device_class': 'battery',
                'state_topic': self.data['status_topic'],
                # 'json_attributes_topic': self.data['status_topic'],
                'value_template':
                    '{%- if value_json.battery -%}100{%- else -%}0{%- endif -%}'
                #                    'command_topic': self.data['control_topic']
            }
            ddd['homeassistant/sensor/' + self.data['mac'] + '/battery/config'] = bytearray(json.dumps(discovery), 'utf-8')

            # START - RFWD window/door detector
            if (self.data['device info']['product type'] == 'RFWD-100') or (
                    self.data['device info']['product type'] == 'RFSF-1B'):
                # RFWD-100 status messages
                # {alarm: true, detect: false, tamper: “closed”, automat: false, battery: true, disarm: false}
                # {alarm: true, detect: true, tamper: “closed”, automat: false, battery: true, disarm: false}
                # RFSF-1B
                # {"alarm": false,	"detect": false, "automat": true, "battery": true, "disarm": false }
                # Alarm
                discovery = {
                    'name': self.data['device info']['label'] + 'alarm',
                    'unique_id': ('eLan-' + self.data['mac'] + '-alarm'),
                    'icon': 'mdi:alarm-light',
                    'device': {
                        'name': self.data['device info']['label'],
                        'identifiers': ('eLan-detector-' + self.data['mac']),
                        'connections': [["self.data['mac']", self.data['mac']]],
                        'mf': 'Elko EP',
                        'mdl': self.data['device info']['product type']
                    },
                    'state_topic': self.data['status_topic'],
                    'json_attributes_topic': self.data['status_topic'],
                    'value_template':
                        '{%- if value_json.alarm -%}on{%- else -%}off{%- endif -%}'
                    #                    'command_topic': self.data['control_topic']
                }
                ddd['homeassistant/sensor/' + self.data['mac'] + '/alarm/config'] = bytearray(json.dumps(discovery), 'utf-8')

            if self.data['device info']['product type'] == 'RFWD-100':
                # Tamper
                # RFWD-100 status messages
                # {alarm: true, detect: false, tamper: “closed”, automat: false, battery: true, disarm: false}
                # {alarm: true, detect: true, tamper: “closed”, automat: false, battery: true, disarm: false}
                discovery = {
                    'name': self.data['device info']['label'] + 'tamper',
                    'unique_id': ('eLan-' + self.data['mac'] + '-tamper'),
                    'icon': 'mdi:gesture-tap',
                    'device': {
                        'name': self.data['device info']['label'],
                        'identifiers': ('eLan-detector-' + self.data['mac']),
                        'connections': [["self.data['mac']", self.data['mac']]],
                        'mf': 'Elko EP',
                        'mdl': self.data['device info']['product type']
                    },
                    'state_topic': self.data['status_topic'],
                    'json_attributes_topic': self.data['status_topic'],
                    'value_template':
                        '{%- if value_json.tamper == "opened" -%}on{%- else -%}off{%- endif -%}'
                    #                    'command_topic': self.data['control_topic']
                }

                ddd['homeassistant/sensor/' + self.data['mac'] + '/tamper/config'] = bytearray(json.dumps(discovery), 'utf-8')


                # Automat
                discovery = {
                    'name': self.data['device info']['label'] + 'automat',
                    'unique_id': ('eLan-' + self.data['mac'] + '-automat'),
                    'icon': 'mdi:arrow-decision-auto',
                    'device': {
                        'name': self.data['device info']['label'],
                        'identifiers': ('eLan-detector-' + self.data['mac']),
                        'connections': [["self.data['mac']", self.data['mac']]],
                        'mf': 'Elko EP',
                        'mdl': self.data['device info']['product type']
                    },
                    'state_topic': self.data['status_topic'],
                    'json_attributes_topic': self.data['status_topic'],
                    'value_template':
                        '{%- if value_json.automat -%}on{%- else -%}off{%- endif -%}'
                    #                    'command_topic': self.data['control_topic']
                }
                ddd['homeassistant/sensor/' + self.data['mac'] + '/automat/config'] = bytearray(json.dumps(discovery), 'utf-8')


                # Disarm
                discovery = {
                    'name': self.data['device info']['label'] + 'disarm',
                    'unique_id': ('eLan-' + self.data['mac'] + '-disarm'),
                    'icon': 'mdi:lock-alert',
                    'device': {
                        'name': self.data['device info']['label'],
                        'identifiers': ('eLan-detector-' + self.data['mac']),
                        'connections': [["self.data['mac']", self.data['mac']]],
                        'mf': 'Elko EP',
                        'mdl': self.data['device info']['product type']
                    },
                    'state_topic': self.data['status_topic'],
                    'json_attributes_topic': self.data['status_topic'],
                    'value_template':
                        '{%- if value_json.disarm -%}on{%- else -%}off{%- endif -%}'
                    #                    'command_topic': self.data['control_topic']
                }
                ddd['homeassistant/sensor/' + self.data['mac'] + '/disarm/config'] = bytearray(json.dumps(discovery), 'utf-8')
                self.data['discovery'] = ddd

    async def publish(self):
        try:
            resp = elan.get(self.url + '/state')
            await mqtt.publish(self.status_topic, bytearray(json.dumps(resp), 'utf-8'))
            logger.info("{} has been published".format(self.url))
        except BaseException as be:
            logger.error("publishing of {} failed {}".format(self.url, str(be)))


    async def discover(self):
        if "discovery" not in self.data:
            logger.warning("no discovery for {}".format(self.data['url']))
            return
        for topic, data in self.discovery.items():
            await mqtt.publish(topic, data)
        logger.info("{} has been set to discovered".format(self.url))

    async def process_command(self, data):
        # print("Got message:", topic, data)
        try:

            # post command to device - warning there are no checks
            logger.debug("processing: {}, {}".format(self.url, data))
            # data = json.loads(data)
            #resp: Response = elan_cli.put(d[tmp[1]]['url'], data=data)
            #command_info = resp.text
            command_info: str = elan.put(self.url, data=data)
            # print(resp)
            logger.debug(command_info)
            # check and publish updated state of device
            await self.publish()
        except BaseException as be:
            logger.error("publishing of {} failed {}".format(self.url, str(be)))

