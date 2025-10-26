from elan_client import ElanClient
from mqtt_client import MqttClient

import logging
import json


logger: logging.Logger = logging.getLogger(__name__)


class Device:
    """one eLan device"""
    data: dict = {}
    elan: ElanClient = None
    mqtt: MqttClient = None

    def __getattr__(self, item: str):
        if item in self.data:
            return self.data[item]
        return None

    @classmethod
    def init(cls, elan: ElanClient, mqtt: MqttClient):
        cls.elan = elan
        cls.mqtt = mqtt

    def set_discovery(self, type, *args):
        getattr(self, f"_discovery_{type}")()

    @classmethod
    def create(cls, url: str):
        self = cls()
        try:
            info = self.elan.get(url)

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

        d_type = self.data['device info']['type']
        d_product = self.data['device info']['product type']

        kind = 'unknown'
        if d_product == 'RFDA-11B':
            kind = "light"
        elif d_type in ("light", "lamp"):
            kind = "light"
        if 'brightness' in self.data['primary actions']:
            kind = "light"
        elif d_product in ('RFSA-61M',  'RFSA-66M', 'RFSA-11B', 'RFUS-61', 'RFSA-62B'):
            kind = "switch"
        elif d_type == 'appliance':
            kind = "switch"
        elif d_product == 'RFTI-10B':
            kind = "thermometer"
        elif d_type == "thermometer":
            kind = "thermometer"
        elif d_product == 'RFSTI-11G':
            kind = "thermostat"
        elif d_type == 'heating':
            kind = "thermostat"
        elif d_product == "RFATV-1":
            kind = "regulator"
        elif d_type == "temperature regulation area":
            kind = "regulator"
        elif d_type == 'detector':
            kind = "detector"
        elif  ('RFWD-' in d_product) or (
                'RFSD-' in d_product) or (
                'RFMD-' in d_product) or (
                'RFSF-' in d_product):
            kind = "detector"

        # START - RFWD window/door detector
        elif d_type == 'RFWD-100':
            kind = "alarm"
        elif d_product == 'RFSF-1B':
            kind = "alarm"
        logger.debug("device type: '{}', product type: '{}', kind: '{}'".format(d_type, d_product, kind))

        self.set_discovery(kind)

        return self

    def _discovery_light(self):
        ddd = {}
        if "on" in self.data["primary actions"]:
            logger.debug("Primary action of light is ON")
            discovery = {
                "schema": "basic",
                "name": self.data["device info"]["label"],
                "unique_id": ("eLan-" + self.data["mac"]),
                "device": {
                    "name": self.data["device info"]["label"],
                    "identifiers": ("eLan-light-" + self.data["mac"]),
                    "connections": [["self.data['mac']", self.data["mac"]]],
                    "mf": "Elko EP",
                    "mdl": self.data["device info"]["product type"],
                },
                "command_topic": self.data["control_topic"],
                "state_topic": self.data["status_topic"],
                "json_attributes_topic": self.data["status_topic"],
                "payload_off": '{"on":false}',
                "payload_on": '{"on":true}',
                "state_value_template": '{%- if value_json.on -%}{"on":true}{%- else -%}{"on":false}{%- endif -%}',
            }
            ddd["homeassistant/light/" + self.data["mac"] + "/config"] = json.dumps(discovery)
            self.data["discovery"] = ddd

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
            ddd['homeassistant/light/' + self.data['mac'] + '/config'] = json.dumps(discovery)
            self.data['discovery'] = ddd



    def _discovery_switch(self):
        ddd = {}
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
            ddd['homeassistant/switch/' + self.data['mac'] + '/config'] = json.dumps(discovery)
            self.data['discovery'] = ddd



    def _discovery_thermostat(self):
        ddd = {}
        discovery = {
            "name": self.data["device info"]["label"] + "-IN",
            "unique_id": ("eLan-" + self.data["mac"] + "-IN"),
            "device": {
                "name": self.data["device info"]["label"],
                "identifiers": ("eLan-thermostat-" + self.data["mac"]),
                "connections": [["self.data['mac']", self.data["mac"]]],
                "mf": "Elko EP",
                "mdl": self.data["device info"]["product type"],
            },
            "device_class": "temperature",
            "state_topic": self.data["status_topic"],
            "json_attributes_topic": self.data["status_topic"],
            "value_template": '{{ value_json["temperature IN"] }}',
            "unit_of_measurement": "°C",
        }
        ddd["homeassistant/sensor/" + self.data["mac"] + "/IN/config"] = json.dumps(discovery)

        discovery = {
            "name": self.data["device info"]["label"] + "-OUT",
            "unique_id": ("eLan-" + self.data["mac"] + "-OUT"),
            "device": {
                "name": self.data["device info"]["label"],
                "identifiers": ("eLan-thermostat-" + self.data["mac"]),
                "connections": [["self.data['mac']", self.data["mac"]]],
                "mf": "Elko EP",
                "mdl": self.data["device info"]["product type"],
            },
            "state_topic": self.data["status_topic"],
            "json_attributes_topic": self.data["status_topic"],
            "device_class": "temperature",
            "value_template": '{{ value_json["temperature OUT"] }}',
            "unit_of_measurement": "°C",
        }
        ddd["homeassistant/sensor/" + self.data["mac"] + "/OUT/config"] = json.dumps(discovery)
        self.data["discovery"] = ddd



    #
    # Thermometers
    #
    # User should set type to thermometer. But sometimes...
    #
    def _discovery_thermometer(self):
        ddd = {}

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
        ddd['homeassistant/sensor/' + self.data['mac'] + '/IN/config'] = json.dumps(discovery)

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
        ddd['homeassistant/sensor/' + self.data['mac'] + '/OUT/config'] = json.dumps(discovery)
        self.data['discovery'] = ddd


        #
        # Detectors
        #
        # RFWD-100 status messages
        # {alarm: true, detect: false, tamper: “closed”, automat: false, battery: true, disarm: false}
        # {alarm: true, detect: true, tamper: “closed”, automat: false, battery: true, disarm: false}
        # RFSF-1B status message
        # {"alarm": false,	"detect": false, "automat": true, "battery": true, "disarm": false }

    def _discovery_detector(self):
        ddd = {}
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

        ddd['homeassistant/sensor/' + self.data['mac'] + '/config'] = json.dumps(discovery)

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
        ddd['homeassistant/sensor/' + self.data['mac'] + '/battery/config'] = json.dumps(discovery)



    def _discovery_window(self):
        ddd = {}

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
        ddd['homeassistant/sensor/' + self.data['mac'] + '/alarm/config'] = json.dumps(discovery)

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

            ddd['homeassistant/sensor/' + self.data['mac'] + '/tamper/config'] = json.dumps(discovery)

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
            ddd['homeassistant/sensor/' + self.data['mac'] + '/automat/config'] = json.dumps(discovery)

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
            ddd['homeassistant/sensor/' + self.data['mac'] + '/disarm/config'] = json.dumps(discovery)
            self.data['discovery'] = ddd




    def _discovery_regulator(self):
        ddd = {}
        discovery = {
            "name": self.data["device info"]["label"] + "regulator",
            "unique_id": ("eLan-" + self.data["mac"] + "-regulator"),
            "icon": "mdi:lock-alert",
            "device": {
                "name": self.data["device info"]["label"],
                "identifiers": ("eLan-detector-" + self.data["mac"]),
                "connections": [["self.data['mac']", self.data["mac"]]],
                "mf": "Elko EP",
                "mdl": self.data["device info"]["product type"],
            },
            "device_class": "temperature",
            "state_topic": self.data["status_topic"],
            "json_attributes_topic": self.data["status_topic"],
            "value_template": '{{ value_json["temperature"] }}',
            "unit_of_measurement": "°C"
        }
        ddd["homeassistant/sensor/" + self.data["mac"] + "/regulator/config"] = json.dumps(discovery)
        self.data["discovery"] = ddd


    def set_discovery2(self):
        ddd = {}
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
                ddd['homeassistant/light/' + self.data['mac'] + '/config'] = json.dumps(discovery)
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
                ddd['homeassistant/light/' + self.data['mac'] + '/config'] = json.dumps(discovery)
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
                ddd['homeassistant/switch/' + self.data['mac'] + '/config'] = json.dumps(discovery)
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
            ddd['homeassistant/sensor/' + self.data['mac'] + '/IN/config'] = json.dumps(discovery)

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
            ddd['homeassistant/sensor/' + self.data['mac'] + '/OUT/config'] = json.dumps(discovery)
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
            ddd['homeassistant/sensor/' + self.data['mac'] + '/IN/config'] = json.dumps(discovery)

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
            ddd['homeassistant/sensor/' + self.data['mac'] + '/OUT/config'] = json.dumps(discovery)
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

            ddd['homeassistant/sensor/' + self.data['mac'] + '/config'] = json.dumps(discovery)

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
            ddd['homeassistant/sensor/' + self.data['mac'] + '/battery/config'] = json.dumps(discovery)

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
                ddd['homeassistant/sensor/' + self.data['mac'] + '/alarm/config'] = json.dumps(discovery)

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

                ddd['homeassistant/sensor/' + self.data['mac'] + '/tamper/config'] = json.dumps(discovery)

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
                ddd['homeassistant/sensor/' + self.data['mac'] + '/automat/config'] = json.dumps(discovery)

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
                ddd['homeassistant/sensor/' + self.data['mac'] + '/disarm/config'] = json.dumps(discovery)
                self.data['discovery'] = ddd

    def publish(self):
        """publish device state to mqtt"""
        try:
            resp = self.elan.get(self.url + '/state')
            self.mqtt.publish(self.status_topic, json.dumps(resp), "status")
            logger.info("{} has been published".format(self.url))
        except BaseException as be:
            logger.error("publishing of {} failed {}".format(self.url, str(be)))

    async def discover(self):
        """publish device discovery info to mqtt"""
        if "discovery" not in self.data:
            logger.warning("no discovery data for {} available".format(self.data['url']))
            return
        for topic, data in self.discovery.items():
            self.mqtt.publish(topic, data, "discovery")
        logger.info("{} has been set to discovered".format(self.url))

    async def process_command(self, data: str):
        """send command to elan and mqtt"""
        # print("Got message:", topic, data)
        try:

            # post command to device - warning there are no checks
            logger.debug("processing: {}, {}".format(self.url, data))
            # data = json.loads(data)
            #resp: Response = elan_cli.put(d[tmp[1]]['url'], data=data)
            #command_info = resp.text
            command_info: str = self.elan.put(self.url, data=data)
            # print(resp)
            logger.debug(command_info)
            # check and publish updated state of device
            self.publish()
        except BaseException as be:
            logger.error("publishing of {} failed {}".format(self.url, str(be)))
